"""Tests for Phase 4: Durable Tenant-Scoped Audit Logging, Hash Chaining, Redaction, and Querying."""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.models import (
    AgentCredentialModel,
    AgentModel,
    AuditEventModel,
    MembershipModel,
    OrganizationModel,
    ProjectModel,
    UserModel,
)
from agent_security.db.session import close_db, get_session_maker, init_db
from agent_security.main import create_app
from agent_security.security.credentials import generate_agent_credential
from agent_security.services.audit_service import AuditService


@pytest.fixture(scope="module")
def app_and_client():
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_secret_key_minimum_32_characters_long_123",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_p4?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.asyncio
async def test_audit_lifecycle_and_hash_chain(app_and_client):
    client = app_and_client
    await init_db()
    session_maker = get_session_maker()

    # 1. Setup seed organizations and users
    async with session_maker() as db:
        org1 = OrganizationModel(id="org_alpha", name="Alpha Corp", status="active")
        org2 = OrganizationModel(id="org_beta", name="Beta Corp", status="active")
        proj1 = ProjectModel(id="proj_alpha", organization_id="org_alpha", name="Alpha Project", status="active")
        proj2 = ProjectModel(id="proj_beta", organization_id="org_beta", name="Beta Project", status="active")
        admin = UserModel(id="usr_admin", email="admin@corp.internal", display_name="Admin User", status="active")
        mem1 = MembershipModel(id="mem_1", user_id="usr_admin", organization_id="org_alpha", role="administrator")
        db.add_all([org1, org2, proj1, proj2, admin, mem1])
        await db.commit()

    admin_headers = {"X-User-Email": "admin@corp.internal"}

    # 2. Create agent -> generates agent.created audit record
    create_agent_resp = client.post(
        "/api/v1/agents",
        json={
            "id": "agt_audit_01",
            "organization_id": "org_alpha",
            "project_id": "proj_alpha",
            "name": "Audit Worker",
            "environment": "production",
            "purpose": "Testing audit log trail",
        },
        headers=admin_headers,
    )
    assert create_agent_resp.status_code == 201, create_agent_resp.text

    # 3. Create initial credential
    cred_resp = client.post(
        "/api/v1/agents/agt_audit_01/credentials",
        headers=admin_headers,
    )
    assert cred_resp.status_code == 201
    plain_secret = cred_resp.json()["plaintext_secret"]

    # 4. Rotate credential -> generates agent.credential_rotated audit record
    rotate_resp = client.post(
        "/api/v1/agents/agt_audit_01/credentials/rotate",
        headers=admin_headers,
    )
    assert rotate_resp.status_code == 201
    new_secret = rotate_resp.json()["plaintext_secret"]

    # 5. Start session -> generates session.started audit record
    agent_auth_headers = {
        "Authorization": f"Bearer {new_secret}",
    }
    session_resp = client.post(
        "/api/v1/sessions",
        params={"expires_in_seconds": 3600},
        headers=agent_auth_headers,
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]

    # 6. Evaluate action with sensitive payload (passwords, tokens)
    # Redaction engine should sanitize details before persisting
    eval_resp = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "tool": "safe_echo",
            "operation": "read",
            "resource": "public_data",
            "arguments": {
                "query": "search",
                "password": "SuperSecretPassword123!",
                "api_key": "mock_test_key_1234567890abcdef",
                "auth_header": "Bearer secret_jwt_token_value_xyz",
            },
        },
        headers=agent_auth_headers,
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["decision"] == "ALLOW"
    action_id = eval_data["action_id"]
    auth_token = eval_data["execution_authorization"]

    # 7. Execute action -> generates action.executed audit record
    exec_resp = client.post(
        f"/api/v1/runtime/actions/{action_id}/execute",
        json={"execution_authorization": auth_token},
        headers=agent_auth_headers,
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "EXECUTED"

    # 8. Terminate session -> generates session.terminated audit record
    term_resp = client.patch(
        f"/api/v1/sessions/{session_id}/terminate",
        headers=agent_auth_headers,
    )
    assert term_resp.status_code == 200

    # 9. Query audit events API: verify tenant scoping and event presence
    audit_resp = client.get(
        "/api/v1/audit/events",
        params={"organization_id": "org_alpha"},
        headers=admin_headers,
    )
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    assert len(events) >= 6

    event_types = [e["event_type"] for e in events]
    assert "agent.created" in event_types
    assert "agent.credential_created" in event_types
    assert "agent.credential_rotated" in event_types
    assert "session.started" in event_types
    assert "action.evaluated" in event_types
    assert "action.executed" in event_types
    assert "session.terminated" in event_types

    # 10. Verify tenant isolation: querying org_beta by org_alpha admin is rejected
    beta_resp = client.get(
        "/api/v1/audit/events",
        params={"organization_id": "org_beta"},
        headers=admin_headers,
    )
    assert beta_resp.status_code == 403

    # Querying without organization_id returns only authorized org_alpha events
    unscoped_resp = client.get("/api/v1/audit/events", headers=admin_headers)
    assert unscoped_resp.status_code == 200
    assert all(e["organization_id"] == "org_alpha" for e in unscoped_resp.json())

    # 11. Verify redaction in audit event payload
    action_eval_event = next(e for e in events if e["event_type"] == "action.evaluated")
    stored_args = action_eval_event["details"]["arguments"]
    assert stored_args["password"] == "[REDACTED_SECRET]"
    assert stored_args["api_key"] == "[REDACTED_SECRET]"
    assert stored_args["auth_header"] == "[REDACTED_SECRET]"
    assert "SuperSecretPassword123!" not in str(action_eval_event["details"])

    # 12. Verify hash chain integrity for org_alpha
    verify_resp = client.get(
        "/api/v1/audit/verify-chain",
        params={"organization_id": "org_alpha"},
        headers=admin_headers,
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["valid"] is True
    assert verify_data["verified_count"] >= 6
    assert verify_data["error"] is None

    # 13. Verify tamper detection: alter one record in database and re-verify
    async with session_maker() as db:
        # Fetch an event and tamper its details
        tamper_event = (await db.execute(
            select(AuditEventModel).where(AuditEventModel.organization_id == "org_alpha").limit(1)
        )).scalar_one()
        tamper_event.details = {"tampered": True}
        await db.commit()

    tamper_verify_resp = client.get(
        "/api/v1/audit/verify-chain",
        params={"organization_id": "org_alpha"},
        headers=admin_headers,
    )
    assert tamper_verify_resp.status_code == 200
    tamper_data = tamper_verify_resp.json()
    assert tamper_data["valid"] is False
    assert "mismatch" in tamper_data["error"].lower() or "tamper" in tamper_data["error"].lower() or "broken" in tamper_data["error"].lower()


@pytest.mark.asyncio
async def test_audit_approval_workflow(app_and_client):
    client = app_and_client
    session_maker = get_session_maker()

    plain_secret, secret_hash = generate_agent_credential()
    async with session_maker() as db:
        org = OrganizationModel(id="org_audit_hitl", name="HITL Audit Org", status="active")
        proj = ProjectModel(id="proj_audit_hitl", organization_id="org_audit_hitl", name="Audit HITL Project", status="active")
        agent = AgentModel(
            id="agt_audit_hitl", organization_id="org_audit_hitl", project_id="proj_audit_hitl",
            name="HITL Agent", owner="developer@corp.internal", status="active"
        )
        cred = AgentCredentialModel(id="cred_audit_hitl", agent_id="agt_audit_hitl", secret_hash=secret_hash, is_active=True)
        approver = UserModel(id="usr_approver_audit", email="approver@corp.internal", display_name="HITL Approver", status="active")
        mem = MembershipModel(id="mem_appr_audit", user_id="usr_approver_audit", organization_id="org_audit_hitl", role="approver")
        db.add_all([org, proj, agent, cred, approver, mem])
        await db.commit()

    agent_headers = {"Authorization": f"Bearer {plain_secret}"}
    approver_headers = {"X-User-Email": "approver@corp.internal"}

    # Start session
    sess_res = client.post("/api/v1/sessions", headers=agent_headers)
    assert sess_res.status_code == 201
    sess_id = sess_res.json()["session_id"]

    # Trigger action requiring approval (mutation)
    eval_res = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={
            "session_id": sess_id,
            "tool": "production_database",
            "operation": "update",
            "resource": "billing_status",
            "arguments": {"customer_id": "cust_123", "status": "active"},
        },
        headers=agent_headers,
    )
    assert eval_res.status_code == 200
    ticket_id = eval_res.json()["approval_ticket_id"]
    assert ticket_id is not None

    # Approve action
    appr_res = client.post(
        f"/api/v1/approvals/{ticket_id}/approve",
        json={"rationale": "Verified customer payment manually"},
        headers=approver_headers,
    )
    assert appr_res.status_code == 200

    # Query audit events
    audit_res = client.get(
        "/api/v1/audit/events",
        params={"organization_id": "org_audit_hitl"},
        headers=approver_headers,
    )
    assert audit_res.status_code == 200
    events = audit_res.json()
    event_types = [e["event_type"] for e in events]
    assert "approval.approved" in event_types
    appr_event = next(e for e in events if e["event_type"] == "approval.approved")
    assert appr_event["details"]["ticket_id"] == ticket_id
    assert appr_event["details"]["approver_id"] == "usr_approver_audit"
