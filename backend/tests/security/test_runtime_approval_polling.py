"""Tests for Agent-Facing Approval Polling Endpoint: GET /api/v1/runtime/approvals/{ticket_id}."""

import asyncio
from datetime import datetime, timezone
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
def app_and_client():
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_secret_key_minimum_32_characters_long_123",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_polling?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


def test_runtime_approval_polling_lifecycle(app_and_client):
    async def _run():
        client = app_and_client
        await init_db()
        session_maker = get_session_maker()

        agent1_secret, agent1_hash = generate_agent_credential()
        agent2_secret, agent2_hash = generate_agent_credential()

        async with session_maker() as db:
            org = OrganizationModel(id="org_polling", name="Polling Org", status="active")
            proj = ProjectModel(id="proj_polling", organization_id="org_polling", name="Polling Project", status="active")
            user = UserModel(id="usr_admin", email="admin@polling.internal", display_name="Admin", status="active")
            membership = MembershipModel(
                id="mem_admin",
                organization_id="org_polling",
                user_id="usr_admin",
                role="administrator",
            )

            agent1 = AgentModel(
                id="agent_1",
                organization_id="org_polling",
                project_id="proj_polling",
                name="Agent One",
                owner="dev@polling.internal",
                status="active",
            )
            cred1 = AgentCredentialModel(
                id="cred_1",
                agent_id="agent_1",
                secret_hash=agent1_hash,
                is_active=True,
            )

            agent2 = AgentModel(
                id="agent_2",
                organization_id="org_polling",
                project_id="proj_polling",
                name="Agent Two",
                owner="other@polling.internal",
                status="active",
            )
            cred2 = AgentCredentialModel(
                id="cred_2",
                agent_id="agent_2",
                secret_hash=agent2_hash,
                is_active=True,
            )

            db.add_all([org, proj, user, membership, agent1, cred1, agent2, cred2])
            await db.commit()

        agent1_headers = {"Authorization": f"Bearer {agent1_secret}"}
        agent2_headers = {"Authorization": f"Bearer {agent2_secret}"}
        admin_headers = {"X-User-Email": "admin@polling.internal"}

        # Start session for agent 1
        sess_res = client.post("/api/v1/runtime/sessions", headers=agent1_headers)
        assert sess_res.status_code == 201
        session_id = sess_res.json()["session_id"]

        # Submit an action requiring approval (mutation: write)
        eval_res = client.post(
            "/api/v1/runtime/actions/evaluate",
            headers=agent1_headers,
            json={
                "session_id": session_id,
                "tool": "database",
                "operation": "write",
                "resource": "ledger_table",
                "arguments": {"mutation": "UPDATE balance SET amount = 1000"},
                "purpose": "Deploy payment record",
            },
        )
        assert eval_res.status_code == 200
        eval_data = eval_res.json()
        assert eval_data["decision"] == "REQUIRE_APPROVAL"
        ticket_id = eval_data["approval_ticket_id"]
        action_id = eval_data["action_id"]
        assert ticket_id is not None

        # 1. TEST: Pending ticket returns status PENDING with no token
        poll_pending = client.get(f"/api/v1/runtime/approvals/{ticket_id}", headers=agent1_headers)
        assert poll_pending.status_code == 200
        pending_data = poll_pending.json()
        assert pending_data["status"] == "PENDING"
        assert "execution_authorization" not in pending_data

        # 2. TEST: Wrong agent gets 404
        poll_wrong_agent = client.get(f"/api/v1/runtime/approvals/{ticket_id}", headers=agent2_headers)
        assert poll_wrong_agent.status_code == 404

        # Approve ticket via HITL control plane
        approve_res = client.post(
            f"/api/v1/approvals/{ticket_id}/approve",
            headers=admin_headers,
            json={"rationale": "Approved after manual audit of ledger update"},
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "APPROVED"

        # 3. TEST: Approved ticket returns status APPROVED with token
        poll_approved = client.get(f"/api/v1/runtime/approvals/{ticket_id}", headers=agent1_headers)
        assert poll_approved.status_code == 200
        approved_data = poll_approved.json()
        assert approved_data["status"] == "APPROVED"
        exec_token = approved_data.get("execution_authorization")
        assert exec_token is not None
        assert len(exec_token) > 20

        # 4. TEST: Execution with approved token succeeds
        exec_res = client.post(
            f"/api/v1/runtime/actions/{action_id}/execute",
            headers=agent1_headers,
            json={"execution_authorization": exec_token},
        )
        assert exec_res.status_code == 200
        assert exec_res.json()["status"] in {"EXECUTED", "EXECUTION_CLAIMED"}

        # 5. TEST: Reuse is rejected (token is single-use)
        # Re-polling after use no longer returns active authorization token
        poll_after_use = client.get(f"/api/v1/runtime/approvals/{ticket_id}", headers=agent1_headers)
        assert poll_after_use.status_code == 200
        assert "execution_authorization" not in poll_after_use.json()

        # Replaying token against another action must fail
        reused_exec = client.post(
            "/api/v1/runtime/actions/act_unrelated_123/execute",
            headers=agent1_headers,
            json={"execution_authorization": exec_token},
        )
        assert reused_exec.status_code in (403, 404)

    asyncio.run(_run())
