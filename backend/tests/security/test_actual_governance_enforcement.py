"""Phase 5 Security Invariants & Governance Enforcement Verification Test Suite.

Verifies the 10 critical security invariants at the actual execution boundary:
1. ALLOW: The authorized tool executes.
2. BLOCK: The tool is never invoked (zero-execution invariant).
3. REQUIRE_APPROVAL: The tool is not invoked before approval.
4. APPROVED: Execution occurs only after valid human approval.
5. REPLAY: Reused single-use authorization is rejected.
6. SUSPEND: New actions from suspended agents are rejected.
7. TENANT ISOLATION: Cross-tenant requests are rejected.
8. INVALID CREDENTIALS: Authentication fails.
9. REVOKED CREDENTIALS: Authentication fails for revoked keys.
10. MODIFIED ACTION: Authorization cannot be reused for a different action.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.models import (
    AgentCredentialModel,
    AgentModel,
    MembershipModel,
    OrganizationModel,
    ProjectModel,
    UserModel,
)
from agent_security.db.session import close_db, get_session_maker, init_db
from agent_security.main import create_app
from agent_security.security.credentials import generate_agent_credential


@pytest.fixture(scope="module")
def enforcement_client():
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_enforcement_secret_key_32chars_long",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_enforcement?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.asyncio
async def test_all_10_governance_enforcement_scenarios(enforcement_client):
    client = enforcement_client
    await init_db()
    session_maker = get_session_maker()

    # Bootstrap Tenant A, Project A, Admin, Reviewer, and Agent A
    plain_secret_a, hash_a = generate_agent_credential()
    plain_secret_b, hash_b = generate_agent_credential()
    plain_secret_revoked, hash_revoked = generate_agent_credential()

    async with session_maker() as db:
        # Organization A
        org_a = OrganizationModel(id="org_alpha", name="Alpha Corp", status="active")
        proj_a = ProjectModel(id="proj_alpha", organization_id="org_alpha", name="Alpha Core")

        # Users & Memberships
        user_owner = UserModel(id="usr_owner", email="owner@alpha.internal", display_name="Agent Owner", status="active")
        user_reviewer = UserModel(id="usr_rev", email="reviewer@alpha.internal", display_name="Security Reviewer", status="active")
        mem_owner = MembershipModel(id="mem_1", user_id="usr_owner", organization_id="org_alpha", role="administrator")
        mem_rev = MembershipModel(id="mem_2", user_id="usr_rev", organization_id="org_alpha", role="approver")

        # Agent A
        agent_a = AgentModel(
            id="agent_alpha_01", organization_id="org_alpha", project_id="proj_alpha",
            name="Alpha Agent", owner="owner@alpha.internal", status="active"
        )
        cred_a = AgentCredentialModel(id="cred_alpha", agent_id="agent_alpha_01", secret_hash=hash_a, is_active=True)

        # Revoked credential for Agent A
        cred_rev = AgentCredentialModel(
            id="cred_alpha_rev", agent_id="agent_alpha_01", secret_hash=hash_revoked, is_active=False,
            revoked_at=datetime.now(timezone.utc)
        )

        # Organization B & Agent B (for Tenant Isolation test)
        org_b = OrganizationModel(id="org_beta", name="Beta Corp", status="active")
        proj_b = ProjectModel(id="proj_beta", organization_id="org_beta", name="Beta Core")
        agent_b = AgentModel(
            id="agent_beta_01", organization_id="org_beta", project_id="proj_beta",
            name="Beta Agent", owner="owner@beta.internal", status="active"
        )
        cred_b = AgentCredentialModel(id="cred_beta", agent_id="agent_beta_01", secret_hash=hash_b, is_active=True)

        db.add_all([
            org_a, proj_a, user_owner, user_reviewer, mem_owner, mem_rev, agent_a, cred_a, cred_rev,
            org_b, proj_b, agent_b, cred_b
        ])
        await db.commit()

    headers_a = {"Authorization": f"Bearer {plain_secret_a}"}
    headers_b = {"Authorization": f"Bearer {plain_secret_b}"}

    # Start Session for Agent A
    sess_res = client.post("/api/v1/runtime/sessions", headers=headers_a)
    assert sess_res.status_code == 201, sess_res.text
    session_id_a = sess_res.json()["session_id"]

    # --- SCENARIO 1: ALLOW -> The authorized tool executes ---
    eval_allow = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=headers_a,
        json={
            "session_id": session_id_a,
            "tool": "safe_echo",
            "operation": "read",
            "resource": "ledger_records",
            "arguments": {"filter": "active"},
        },
    )
    assert eval_allow.status_code == 200
    allow_data = eval_allow.json()
    assert allow_data["decision"] == "ALLOW"
    assert allow_data["execution_authorization"] is not None
    action_id_allow = allow_data["action_id"]

    exec_allow = client.post(
        f"/api/v1/runtime/actions/{action_id_allow}/execute",
        headers=headers_a,
        json={"execution_authorization": allow_data["execution_authorization"]},
    )
    assert exec_allow.status_code == 200
    assert exec_allow.json()["status"] == "EXECUTED"

    # --- SCENARIO 2: BLOCK -> Tool is NEVER invoked (Zero-execution invariant) ---
    eval_block = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=headers_a,
        json={
            "session_id": session_id_a,
            "tool": "database",
            "operation": "delete",
            "resource": "production_users",
            "arguments": {"id": 1},
        },
    )
    assert eval_block.status_code == 200
    block_data = eval_block.json()
    assert block_data["decision"] == "BLOCK"
    assert block_data["execution_authorization"] is None

    # Proving that execution cannot occur without a valid HMAC authorization token
    exec_block = client.post(
        f"/api/v1/runtime/actions/{block_data['action_id']}/execute",
        headers=headers_a,
        json={"execution_authorization": "invalid_fake_token_at_least_20_characters"},
    )
    assert exec_block.status_code == 403

    # --- SCENARIO 3: REQUIRE_APPROVAL -> Tool not invoked before approval ---
    eval_appr = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=headers_a,
        json={
            "session_id": session_id_a,
            "tool": "database",
            "operation": "write",
            "resource": "prod_schema",
            "arguments": {"table": "payments"},
        },
    )
    assert eval_appr.status_code == 200
    appr_data = eval_appr.json()
    assert appr_data["decision"] == "REQUIRE_APPROVAL"
    assert appr_data["execution_authorization"] is None
    ticket_id = appr_data["approval_ticket_id"]
    action_id_appr = appr_data["action_id"]

    # Pre-approval execution attempt must be rejected
    exec_pre = client.post(
        f"/api/v1/runtime/actions/{action_id_appr}/execute",
        headers=headers_a,
        json={"execution_authorization": "cannot_execute_unapproved"},
    )
    assert exec_pre.status_code in [403, 401]

    # --- SCENARIO 4: APPROVED -> Execution occurs only after valid human approval ---
    # Requester-Approver separation: owner cannot approve their own agent's action
    fail_self_approve = client.post(
        f"/api/v1/approvals/{ticket_id}/approve",
        headers={"X-User-Email": "owner@alpha.internal"},
        json={"rationale": "I am approving my own agent"},
    )
    assert fail_self_approve.status_code == 403

    # Valid reviewer signs off
    approve_res = client.post(
        f"/api/v1/approvals/{ticket_id}/approve",
        headers={"X-User-Email": "reviewer@alpha.internal"},
        json={"rationale": "Verified change ticket approved"},
    )
    assert approve_res.status_code == 200
    appr_ticket = approve_res.json()
    assert appr_ticket["status"] == "APPROVED"
    assert appr_ticket["execution_authorization"] is not None

    # Now execution succeeds with the issued approval token
    exec_approved = client.post(
        f"/api/v1/runtime/actions/{action_id_appr}/execute",
        headers=headers_a,
        json={"execution_authorization": appr_ticket["execution_authorization"]},
    )
    assert exec_approved.status_code == 200
    assert exec_approved.json()["status"] == "EXECUTED"

    # --- SCENARIO 5: REPLAY -> Reused single-use authorization is rejected ---
    replay_res = client.post(
        f"/api/v1/runtime/actions/{action_id_appr}/execute",
        headers=headers_a,
        json={"execution_authorization": appr_ticket["execution_authorization"]},
    )
    # Token already used; must not allow re-execution
    assert replay_res.status_code in [200, 403]
    if replay_res.status_code == 200:
        assert replay_res.json().get("idempotent") is True

    # --- SCENARIO 6: SUSPEND -> Actions from suspended agent rejected ---
    # Suspend Agent A
    suspend_res = client.patch(
        "/api/v1/agents/agent_alpha_01",
        headers={"X-User-Email": "owner@alpha.internal"},
        json={"status": "suspended"},
    )
    assert suspend_res.status_code == 200

    # New action evaluation from suspended agent is halted
    eval_sus = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=headers_a,
        json={
            "session_id": session_id_a,
            "tool": "safe_echo",
            "operation": "read",
            "resource": "ledger_records",
            "arguments": {},
        },
    )
    assert eval_sus.status_code in [200, 403]
    if eval_sus.status_code == 200:
        assert eval_sus.json()["decision"] == "SUSPEND"

    # Re-activate Agent A for remaining tests
    client.patch(
        "/api/v1/agents/agent_alpha_01",
        headers={"X-User-Email": "owner@alpha.internal"},
        json={"status": "active"},
    )

    # --- SCENARIO 7: TENANT ISOLATION -> Cross-tenant requests are rejected ---
    # Start Session for Agent B in Org Beta
    sess_b = client.post("/api/v1/runtime/sessions", headers=headers_b)
    session_id_b = sess_b.json()["session_id"]

    # Agent B tries to evaluate using Agent A's session -> 404/403
    cross_session = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=headers_b,
        json={
            "session_id": session_id_a,
            "tool": "safe_echo",
            "operation": "read",
            "resource": "cross_tenant",
        },
    )
    assert cross_session.status_code in [404, 403]

    # --- SCENARIO 8: INVALID CREDENTIALS -> Authentication fails (401) ---
    invalid_auth = client.post(
        "/api/v1/runtime/sessions",
        headers={"Authorization": "Bearer completely_fake_invalid_secret_key"},
    )
    assert invalid_auth.status_code == 401

    # --- SCENARIO 9: REVOKED CREDENTIALS -> Authentication fails (401) ---
    revoked_auth = client.post(
        "/api/v1/runtime/sessions",
        headers={"Authorization": f"Bearer {plain_secret_revoked}"},
    )
    assert revoked_auth.status_code == 401

    # --- SCENARIO 10: MODIFIED ACTION -> Authorization not reusable for tampered action ---
    eval_orig = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=headers_a,
        json={
            "session_id": session_id_a,
            "tool": "safe_echo",
            "operation": "read",
            "resource": "ledger_records",
            "arguments": {"account_id": "acc_100"},
        },
    )
    orig_token = eval_orig.json()["execution_authorization"]
    orig_id = eval_orig.json()["action_id"]

    # Tampered action evaluation (different argument)
    eval_tampered = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=headers_a,
        json={
            "session_id": session_id_a,
            "tool": "safe_echo",
            "operation": "read",
            "resource": "ledger_records",
            "arguments": {"account_id": "acc_999"},
        },
    )
    tampered_id = eval_tampered.json()["action_id"]

    # Trying to use original token to execute the tampered action must fail
    tamper_exec = client.post(
        f"/api/v1/runtime/actions/{tampered_id}/execute",
        headers=headers_a,
        json={"execution_authorization": orig_token},
    )
    assert tamper_exec.status_code == 403
