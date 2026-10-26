"""Tests for Phase 3: HITL Approvals, Requester-Approver Separation, and Multi-Scope Suspension."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.models import (
    AgentCredentialModel,
    AgentModel,
    ApprovalRequestModel,
    MembershipModel,
    OrganizationModel,
    ProjectModel,
    UserModel,
)
from agent_security.db.session import close_db, get_session_maker, init_db
from agent_security.main import create_app
from agent_security.security.credentials import generate_agent_credential


@pytest.fixture(scope="module")
def app_and_client():
    import asyncio
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_secret_key_minimum_32_characters_long_123",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_p3?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.asyncio
async def test_phase3_approvals_and_suspension_matrix(app_and_client):
    client = app_and_client
    await init_db()
    session_maker = get_session_maker()

    now = datetime.now(timezone.utc)
    plain_secret, secret_hash = generate_agent_credential()

    # Setup database records
    async with session_maker() as db:
        org = OrganizationModel(id="org_secops", name="SecOps Org", status="active")
        proj = ProjectModel(id="proj_prod", organization_id="org_secops", name="Production Ops", status="active")
        # Agent owned by devops_lead
        agent = AgentModel(
            id="agt_devops_01", organization_id="org_secops", project_id="proj_prod",
            name="DevOps Agent", owner="devops_lead@corp.internal", status="active"
        )
        cred = AgentCredentialModel(id="cred_dev_01", agent_id="agt_devops_01", secret_hash=secret_hash, is_active=True)

        # Users:
        # 1. devops_lead (Agent Owner / Requester)
        u_owner = UserModel(id="usr_lead", email="devops_lead@corp.internal", display_name="DevOps Lead", status="active")
        mem_owner = MembershipModel(id="mem_01", user_id="usr_lead", organization_id="org_secops", role="administrator")

        # 2. sec_officer (Authorized Approver)
        u_approver = UserModel(id="usr_officer", email="security_officer@corp.internal", display_name="Sec Officer", status="active")
        mem_approver = MembershipModel(id="mem_02", user_id="usr_officer", organization_id="org_secops", role="approver")

        # 3. viewer_user (Unauthorized Role)
        u_viewer = UserModel(id="usr_viewer", email="viewer@corp.internal", display_name="Auditor Viewer", status="active")
        mem_viewer = MembershipModel(id="mem_03", user_id="usr_viewer", organization_id="org_secops", role="viewer")

        db.add_all([org, proj, agent, cred, u_owner, mem_owner, u_approver, mem_approver, u_viewer, mem_viewer])
        await db.commit()

    auth_headers = {"Authorization": f"Bearer {plain_secret}"}

    # Start Session
    sess_res = client.post("/api/v1/runtime/sessions", headers=auth_headers)
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 1. Action that triggers REQUIRE_APPROVAL (mutation / update)
    eval_res = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "tool": "kubernetes",
            "operation": "update",
            "resource": "production_deployment",
            "arguments": {"replicas": 5},
        },
        headers=auth_headers,
    )
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["decision"] == "REQUIRE_APPROVAL"
    ticket_id = eval_data["approval_ticket_id"]
    assert ticket_id is not None
    action_id = eval_data["action_id"]

    # 2. TEST: Unauthorized role (viewer) cannot approve
    unauth_res = client.post(
        f"/api/v1/approvals/{ticket_id}/approve",
        json={"rationale": "Attempted viewer approval"},
        headers={"X-User-Email": "viewer@corp.internal"},
    )
    assert unauth_res.status_code == 403
    assert "not authorized" in unauth_res.json()["error"]["message"].lower()

    # 3. TEST: Requester / Approver separation (agent owner cannot approve own agent's action)
    self_appr_res = client.post(
        f"/api/v1/approvals/{ticket_id}/approve",
        json={"rationale": "I approve my own agent"},
        headers={"X-User-Email": "devops_lead@corp.internal"},
    )
    assert self_appr_res.status_code == 403
    assert "separation" in self_appr_res.json()["error"]["message"].lower()

    # 4. TEST: Authorized approver approves
    appr_res = client.post(
        f"/api/v1/approvals/{ticket_id}/approve",
        json={"rationale": "Scaling deployment approved per ticket SEC-101"},
        headers={"X-User-Email": "security_officer@corp.internal"},
    )
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["status"] == "APPROVED"
    exec_token = appr_data["execution_authorization"]
    assert exec_token is not None

    # 5. TEST: Reused approval (already approved ticket cannot be re-approved)
    reused_res = client.post(
        f"/api/v1/approvals/{ticket_id}/approve",
        json={"rationale": "Re-approving"},
        headers={"X-User-Email": "security_officer@corp.internal"},
    )
    assert reused_res.status_code == 400
    assert "already APPROVED" in reused_res.json()["error"]["message"]

    # 6. TEST: Executing with approved token succeeds
    exec_res = client.post(
        f"/api/v1/runtime/actions/{action_id}/execute",
        json={"execution_authorization": exec_token},
        headers=auth_headers,
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "EXECUTED"

    # 7. TEST: Expired approval ticket
    eval_exp = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "tool": "kubernetes",
            "operation": "update",
            "resource": "ingress",
            "arguments": {"host": "api.corp.internal"},
        },
        headers=auth_headers,
    ).json()
    exp_ticket_id = eval_exp["approval_ticket_id"]

    # Manually expire ticket in DB
    async with session_maker() as db:
        await db.execute(
            ApprovalRequestModel.__table__.update()
            .where(ApprovalRequestModel.ticket_id == exp_ticket_id)
            .values(expires_at=now - timedelta(minutes=5))
        )
        await db.commit()

    exp_res = client.post(
        f"/api/v1/approvals/{exp_ticket_id}/approve",
        json={"rationale": "Late approval"},
        headers={"X-User-Email": "security_officer@corp.internal"},
    )
    assert exp_res.status_code == 400
    assert "expired" in exp_res.json()["error"]["message"].lower()

    # 8. TEST: Rejection flow
    eval_rej = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "tool": "kubernetes",
            "operation": "update",
            "resource": "configmap",
            "arguments": {"key": "val"},
        },
        headers=auth_headers,
    ).json()
    rej_ticket_id = eval_rej["approval_ticket_id"]

    rej_res = client.post(
        f"/api/v1/approvals/{rej_ticket_id}/reject",
        json={"rationale": "Config mutation denied due to freeze period"},
        headers={"X-User-Email": "security_officer@corp.internal"},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"

    # 9. MULTI-SCOPE SUSPENSION TESTS:
    # Scope A: Project suspended -> blocks evaluate & execute
    proj_patch = client.patch("/api/v1/projects/proj_prod", json={"status": "suspended"})
    assert proj_patch.status_code == 200

    susp_eval = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={"session_id": session_id, "tool": "safe_echo", "operation": "read", "resource": "res"},
        headers=auth_headers,
    )
    assert susp_eval.status_code == 403
    assert "project is suspended" in susp_eval.json()["error"]["message"].lower()

    # Resume project
    client.patch("/api/v1/projects/proj_prod", json={"status": "active"})

    # Scope B: Organization suspended -> blocks evaluate & execute
    org_patch = client.patch("/api/v1/organizations/org_secops", json={"status": "suspended"})
    assert org_patch.status_code == 200

    org_susp_eval = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={"session_id": session_id, "tool": "safe_echo", "operation": "read", "resource": "res"},
        headers=auth_headers,
    )
    assert org_susp_eval.status_code == 403
    assert "organization is suspended" in org_susp_eval.json()["error"]["message"].lower()

    # Resume org
    client.patch("/api/v1/organizations/org_secops", json={"status": "active"})
