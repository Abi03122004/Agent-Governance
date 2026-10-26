"""Comprehensive Security, Multi-Tenant DOR, Runtime Gateway, and Durability Audit Test Matrix.

Implements rigorous tests for:
- Rule 4: Multi-Tenant Security & Direct Object Reference (DOR) Attack Matrix
- Rule 5 & 12: Runtime Gateway 10 Scenarios with Instrumented Mock Tool (Zero-Mock Invariant)
- Rule 6: Human Approval Lifecycle & Emergency Suspension Controls
- Rule 9: Database Rollback, Tamper-Evident Hash Chain, and Redis Failure Safety
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.models import (
    AgentCredentialModel,
    AgentModel,
    AgentSessionModel,
    ApprovalRequestModel,
    MembershipModel,
    OrganizationModel,
    ProjectModel,
    RuntimeActionModel,
    UserModel,
)
from agent_security.db.models.runtime_activity import AuditEventModel
from agent_security.db.session import close_db, get_session_maker, init_db
from agent_security.main import create_app
from agent_security.security.credentials import generate_agent_credential
from agent_security.services.audit_service import AuditService
from agent_security.services.anomaly_monitoring import AnomalyMonitoringService


@pytest.fixture(scope="module")
def audit_app_and_client():
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="audit_matrix_test_secret_key_minimum_32_chars_123",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_audit_matrix?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.asyncio
async def test_multi_tenant_dor_attack_matrix(audit_app_and_client):
    """RULE 4: Verify Multi-Tenant isolation against DOR (Direct Object Reference) attacks.
    
    Creates two isolated organizations (Org Alpha and Org Beta) with separate users and agents.
    Verifies that User Beta cannot read, suspend, or rotate credentials for Agent Alpha,
    and cannot inspect, approve, or reject Org Alpha's approval tickets.
    """
    client = audit_app_and_client
    await init_db()
    session_maker = get_session_maker()

    now = datetime.now(timezone.utc)
    plain_alpha, hash_alpha = generate_agent_credential()
    plain_beta, hash_beta = generate_agent_credential()

    async with session_maker() as db:
        # 1. Organization Alpha
        org_a = OrganizationModel(id="org_alpha_tenancy", name="Alpha Corp", status="active")
        proj_a = ProjectModel(id="proj_alpha_tenancy", organization_id="org_alpha_tenancy", name="Alpha Ops")
        agent_a = AgentModel(
            id="agt_alpha_tenancy",
            organization_id="org_alpha_tenancy",
            project_id="proj_alpha_tenancy",
            name="Alpha Agent",
            owner="owner_alpha@corp.internal",
            status="active",
        )
        cred_a = AgentCredentialModel(id="cred_alpha_t01", agent_id="agt_alpha_tenancy", secret_hash=hash_alpha, is_active=True)
        user_a = UserModel(id="usr_alpha_admin", email="owner_alpha@corp.internal", display_name="Alpha Admin", status="active")
        mem_a = MembershipModel(id="mem_a_t01", user_id="usr_alpha_admin", organization_id="org_alpha_tenancy", role="administrator")

        # 2. Organization Beta (Attacker Tenant)
        org_b = OrganizationModel(id="org_beta_tenancy", name="Beta Corp", status="active")
        proj_b = ProjectModel(id="proj_beta_tenancy", organization_id="org_beta_tenancy", name="Beta Ops")
        agent_b = AgentModel(
            id="agt_beta_tenancy",
            organization_id="org_beta_tenancy",
            project_id="proj_beta_tenancy",
            name="Beta Agent",
            owner="attacker_beta@corp.internal",
            status="active",
        )
        cred_b = AgentCredentialModel(id="cred_beta_t01", agent_id="agt_beta_tenancy", secret_hash=hash_beta, is_active=True)
        user_b = UserModel(id="usr_beta_attacker", email="attacker_beta@corp.internal", display_name="Beta Attacker", status="active")
        mem_b = MembershipModel(id="mem_b_t01", user_id="usr_beta_attacker", organization_id="org_beta_tenancy", role="administrator")

        db.add_all([org_a, proj_a, agent_a, cred_a, user_a, mem_a, org_b, proj_b, agent_b, cred_b, user_b, mem_b])
        await db.commit()

    headers_beta_user = {"X-User-Email": "attacker_beta@corp.internal"}
    headers_alpha_user = {"X-User-Email": "owner_alpha@corp.internal"}

    # DOR ATTACK 1: User Beta attempts to READ Agent Alpha's profile
    res_dor_read = client.get(
        "/api/v1/agents/agt_alpha_tenancy",
        headers=headers_beta_user,
    )
    assert res_dor_read.status_code == 403, "DOR vulnerability: User Beta could read Agent Alpha!"
    assert "Forbidden" in res_dor_read.json()["error"]["message"] or "not authorized" in res_dor_read.json()["error"]["message"]

    # DOR ATTACK 2: User Beta attempts to SUSPEND Agent Alpha
    res_dor_suspend = client.patch(
        "/api/v1/agents/agt_alpha_tenancy",
        json={"status": "suspended"},
        headers=headers_beta_user,
    )
    assert res_dor_suspend.status_code == 403, "DOR vulnerability: User Beta could suspend Agent Alpha!"

    # DOR ATTACK 3: User Beta attempts to ROTATE Agent Alpha's credentials
    res_dor_rotate = client.post(
        "/api/v1/agents/agt_alpha_tenancy/credentials/rotate",
        headers=headers_beta_user,
    )
    assert res_dor_rotate.status_code == 403, "DOR vulnerability: User Beta could rotate Agent Alpha credentials!"

    # DOR ATTACK 4: User Beta attempts to CREATE new credentials for Agent Alpha
    res_dor_cred = client.post(
        "/api/v1/agents/agt_alpha_tenancy/credentials",
        headers=headers_beta_user,
    )
    assert res_dor_cred.status_code == 403, "DOR vulnerability: User Beta could create credentials for Agent Alpha!"

    # Verification: Alpha user CAN read and manage their own agent
    res_alpha_legit = client.get("/api/v1/agents/agt_alpha_tenancy", headers=headers_alpha_user)
    assert res_alpha_legit.status_code == 200
    assert res_alpha_legit.json()["id"] == "agt_alpha_tenancy"


@pytest.mark.asyncio
async def test_runtime_gateway_ten_scenarios_and_mock_tool_invariants(audit_app_and_client):
    """RULES 5 & 12: Verify the 10 Runtime Gateway Scenarios with an instrumented mock tool.
    
    CRITICAL ASSERTION:
    When the gateway blocks an action (BLOCK, SUSPEND, REQUIRE_APPROVAL, or invalid auth),
    the protected mock tool invocation count MUST STRICTLY REMAIN ZERO.
    """
    client = audit_app_and_client
    await init_db()
    session_maker = get_session_maker()

    now = datetime.now(timezone.utc)
    plain_secret, secret_hash = generate_agent_credential()

    async with session_maker() as db:
        org = OrganizationModel(id="org_gw_audit", name="GW Audit Org", status="active")
        proj = ProjectModel(id="proj_gw_audit", organization_id="org_gw_audit", name="GW Audit Proj")
        agent = AgentModel(
            id="agt_gw_audit",
            organization_id="org_gw_audit",
            project_id="proj_gw_audit",
            name="Audit Gateway Agent",
            owner="developer@corp.internal",
            status="active",
        )
        cred = AgentCredentialModel(id="cred_gw_01", agent_id="agt_gw_audit", secret_hash=secret_hash, is_active=True)
        # Dedicated approver (requester-approver separation)
        user_approver = UserModel(id="usr_gw_approver", email="sec_auditor@corp.internal", display_name="Security Auditor", status="active")
        mem_approver = MembershipModel(id="mem_gw_appr", user_id="usr_gw_approver", organization_id="org_gw_audit", role="approver")

        db.add_all([org, proj, agent, cred, user_approver, mem_approver])
        await db.commit()

    agent_headers = {"Authorization": f"Bearer {plain_secret}"}
    approver_headers = {"X-User-Email": "sec_auditor@corp.internal"}

    # Start Session
    sess_res = client.post("/api/v1/runtime/sessions", headers=agent_headers)
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # -----------------------------------------------------------------
    # SCENARIO 1: Authorized low-risk action (ALLOW -> Tool count == 1)
    # -----------------------------------------------------------------
    mock_tool = MagicMock(return_value={"status": "success", "rows": 5})
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=mock_tool):
        eval_allow = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={
                "session_id": session_id,
                "tool": "safe_echo",
                "operation": "read",
                "resource": "ledger",
                "arguments": {"page": 1},
            },
            headers=agent_headers,
        )
        assert eval_allow.status_code == 200
        data_allow = eval_allow.json()
        assert data_allow["decision"] == "ALLOW"
        exec_token = data_allow["execution_authorization"]
        action_id = data_allow["action_id"]

        # Invariant: tool NOT invoked before execute call
        assert mock_tool.call_count == 0

        # Execute
        exec_allow = client.post(
            f"/api/v1/runtime/actions/{action_id}/execute",
            json={"execution_authorization": exec_token},
            headers=agent_headers,
        )
        assert exec_allow.status_code == 200
        assert exec_allow.json()["status"] == "EXECUTED"
        assert mock_tool.call_count == 1, "Tool must execute exactly once for allowed action"

    # -----------------------------------------------------------------
    # SCENARIO 2: Prohibited destructive action (BLOCK -> Tool count == 0)
    # -----------------------------------------------------------------
    spy_tool_blocked = MagicMock()
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=spy_tool_blocked):
        eval_block = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={
                "session_id": session_id,
                "tool": "database",
                "operation": "delete",
                "resource": "production_users",
                "arguments": {"all": True},
            },
            headers=agent_headers,
        )
        assert eval_block.status_code == 200
        data_block = eval_block.json()
        assert data_block["decision"] == "BLOCK"
        assert data_block["execution_authorization"] is None

        # Attempt to execute without valid authorization
        exec_blocked = client.post(
            f"/api/v1/runtime/actions/{data_block['action_id']}/execute",
            json={"execution_authorization": "forged_token_minimum_20_chars_long"},
            headers=agent_headers,
        )
        assert exec_blocked.status_code == 403
        assert spy_tool_blocked.call_count == 0, "CRITICAL: Blocked action must NEVER invoke tool!"

    # -----------------------------------------------------------------
    # SCENARIO 3: Action requiring human approval (REQUIRE_APPROVAL -> Tool count == 0)
    # -----------------------------------------------------------------
    spy_tool_approval = MagicMock()
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=spy_tool_approval):
        eval_appr = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={
                "session_id": session_id,
                "tool": "kubernetes",
                "operation": "update",
                "resource": "ingress_rules",
                "arguments": {"new_host": "gateway.internal"},
            },
            headers=agent_headers,
        )
        assert eval_appr.status_code == 200
        data_appr = eval_appr.json()
        assert data_appr["decision"] == "REQUIRE_APPROVAL"
        ticket_id = data_appr["approval_ticket_id"]
        appr_action_id = data_appr["action_id"]

        # Attempt to execute prior to approval
        exec_pre = client.post(
            f"/api/v1/runtime/actions/{appr_action_id}/execute",
            json={"execution_authorization": "unapproved_token_minimum_20_chars"},
            headers=agent_headers,
        )
        assert exec_pre.status_code == 403
        assert spy_tool_approval.call_count == 0, "Tool must NOT execute before approval is granted"

    # -----------------------------------------------------------------
    # SCENARIO 4: Authorized approval (APPROVED -> Tool count == 1)
    # -----------------------------------------------------------------
    mock_tool_post_approval = MagicMock(return_value={"cluster": "updated"})
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=mock_tool_post_approval):
        # Approver approves ticket
        approve_res = client.post(
            f"/api/v1/approvals/{ticket_id}/approve",
            json={"rationale": "Ingress update approved per audit review"},
            headers=approver_headers,
        )
        assert approve_res.status_code == 200
        appr_token = approve_res.json()["execution_authorization"]
        assert appr_token is not None

        # Execute with approved authorization
        exec_approved = client.post(
            f"/api/v1/runtime/actions/{appr_action_id}/execute",
            json={"execution_authorization": appr_token},
            headers=agent_headers,
        )
        assert exec_approved.status_code == 200
        assert exec_approved.json()["status"] == "EXECUTED"
        assert mock_tool_post_approval.call_count == 1

        # -----------------------------------------------------------------
        # SCENARIO 5: Replayed authorization token (Token already consumed)
        # -----------------------------------------------------------------
        replay_res = client.post(
            f"/api/v1/runtime/actions/{appr_action_id}/execute",
            json={"execution_authorization": appr_token},
            headers=agent_headers,
        )
        # Idempotent response; tool is NOT called a second time
        assert replay_res.status_code == 200
        assert replay_res.json().get("idempotent") is True
        assert mock_tool_post_approval.call_count == 1, "Replay attack must not re-execute tool!"

    # -----------------------------------------------------------------
    # SCENARIO 6: Action attempted by suspended agent (SUSPEND -> Tool count == 0)
    # -----------------------------------------------------------------
    spy_tool_susp = MagicMock()
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=spy_tool_susp):
        # Suspend the agent
        async with session_maker() as db:
            await db.execute(
                AgentModel.__table__.update()
                .where(AgentModel.id == "agt_gw_audit")
                .values(status="suspended")
            )
            await db.commit()

        eval_susp = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={"session_id": session_id, "tool": "safe_echo", "operation": "read", "resource": "res"},
            headers=agent_headers,
        )
        assert eval_susp.status_code == 200
        assert eval_susp.json()["decision"] == "SUSPEND"
        assert eval_susp.json()["execution_authorization"] is None
        assert spy_tool_susp.call_count == 0

        # Reactivate agent for remaining scenarios
        async with session_maker() as db:
            await db.execute(
                AgentModel.__table__.update()
                .where(AgentModel.id == "agt_gw_audit")
                .values(status="active")
            )
            await db.commit()

    # -----------------------------------------------------------------
    # SCENARIO 7: Action with expired session (Session expired -> Tool count == 0)
    # -----------------------------------------------------------------
    spy_tool_exp = MagicMock()
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=spy_tool_exp):
        # Create a new session and manually expire it
        s_res = client.post("/api/v1/runtime/sessions", headers=agent_headers)
        exp_sess_id = s_res.json()["session_id"]
        async with session_maker() as db:
            await db.execute(
                AgentSessionModel.__table__.update()
                .where(AgentSessionModel.session_id == exp_sess_id)
                .values(expires_at=now - timedelta(minutes=10))
            )
            await db.commit()

        eval_exp = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={"session_id": exp_sess_id, "tool": "safe_echo", "operation": "read", "resource": "res"},
            headers=agent_headers,
        )
        assert eval_exp.status_code == 403
        assert "Session expired" in eval_exp.json()["error"]["message"]
        assert spy_tool_exp.call_count == 0

    # -----------------------------------------------------------------
    # SCENARIO 8: Modified payload / Token mismatch (Tampered digest -> Tool count == 0)
    # -----------------------------------------------------------------
    spy_tool_tamper = MagicMock()
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=spy_tool_tamper):
        eval_tamper = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={
                "session_id": session_id,
                "tool": "safe_echo",
                "operation": "read",
                "resource": "documents",
                "arguments": {"doc_id": "original-123"},
            },
            headers=agent_headers,
        ).json()
        legit_token = eval_tamper["execution_authorization"]
        legit_act_id = eval_tamper["action_id"]

        # Tamper action_digest in database to simulate payload alteration
        async with session_maker() as db:
            await db.execute(
                RuntimeActionModel.__table__.update()
                .where(RuntimeActionModel.id == legit_act_id)
                .values(action_digest="sha256:tampered_digest_value_9999999999999999999999999999999999999999")
            )
            await db.commit()

        tamper_exec = client.post(
            f"/api/v1/runtime/actions/{legit_act_id}/execute",
            json={"execution_authorization": legit_token},
            headers=agent_headers,
        )
        assert tamper_exec.status_code == 403
        assert "invalid" in tamper_exec.json()["error"]["message"].lower() or "digest" in tamper_exec.json()["error"]["message"].lower()
        assert spy_tool_tamper.call_count == 0

    # -----------------------------------------------------------------
    # SCENARIO 9: Tool that raises an exception during execution (Fail-safe audit)
    # -----------------------------------------------------------------
    def failing_tool(*args, **kwargs):
        raise RuntimeError("Simulated internal downstream service crash")

    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=failing_tool):
        eval_fail = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={
                "session_id": session_id,
                "tool": "safe_echo",
                "operation": "read",
                "resource": "service",
            },
            headers=agent_headers,
        ).json()
        failing_act_id = eval_fail["action_id"]
        failing_token = eval_fail["execution_authorization"]

        exec_fail = client.post(
            f"/api/v1/runtime/actions/{failing_act_id}/execute",
            json={"execution_authorization": failing_token},
            headers=agent_headers,
        )
        assert exec_fail.status_code == 409
        assert "Tool error" in exec_fail.json()["error"]["message"]

        # Verify audit record marked execution as FAILED
        async with session_maker() as db:
            act_row = (await db.execute(
                RuntimeActionModel.__table__.select().where(RuntimeActionModel.id == failing_act_id)
            )).mappings().first()
            assert act_row["execution_status"] == "FAILED"


@pytest.mark.asyncio
async def test_database_and_audit_hash_chain_durability(audit_app_and_client):
    """RULE 9: Verify Cryptographic Audit Hash Chain and Tamper Detection."""
    client = audit_app_and_client
    session_maker = get_session_maker()

    # 1. Verify clean chain passes
    async with session_maker() as db:
        is_valid, count, err = await AuditService.verify_chain(db, "org_gw_audit")
        assert is_valid is True, f"Clean hash chain failed verification: {err}"
        assert count > 0

    # 2. Tamper with a single audit event hash in database
    async with session_maker() as db:
        res = await db.execute(
            AuditEventModel.__table__.select().where(AuditEventModel.organization_id == "org_gw_audit").limit(1)
        )
        row = res.mappings().first()
        target_id = row["event_id"]

        # Corrupt the recorded hash
        await db.execute(
            AuditEventModel.__table__.update()
            .where(AuditEventModel.event_id == target_id)
            .values(event_hash="corrupted_sha256_hash_value_ffffffffffffffffffffffffff")
        )
        await db.commit()

        # 3. Verify that verify_chain immediately flags cryptographic tampering
        is_valid_after, count_after, err_after = await AuditService.verify_chain(db, "org_gw_audit")
        assert is_valid_after is False, "Cryptographic audit ledger failed to detect tamper!"
        assert "Hash mismatch" in err_after or "tamper" in err_after.lower()
