"""Comprehensive Security & Gateway Tests for Phase 2: Runtime Gateway."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.models import (
    AgentCredentialModel,
    AgentModel,
    OrganizationModel,
    ProjectModel,
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
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_gw?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.anyio
async def test_runtime_gateway_complete_flow_and_invariants(app_and_client):
    client = app_and_client
    await init_db()
    session_maker = get_session_maker()

    # 1. Setup Organization, Project, and Agent
    plain_secret, secret_hash = generate_agent_credential()
    async with session_maker() as db:
        org = OrganizationModel(id="org_fintech_gw", name="Fintech Corp", status="active")
        proj = ProjectModel(id="proj_ledger_gw", organization_id="org_fintech_gw", name="Ledger Project")
        agent = AgentModel(
            id="agt_finance_gw", organization_id="org_fintech_gw", project_id="proj_ledger_gw",
            name="Finance Agent", owner="admin@fintech.internal", status="active"
        )
        cred = AgentCredentialModel(
            id="cred_fin_01", agent_id="agt_finance_gw", secret_hash=secret_hash, is_active=True
        )
        db.add_all([org, proj, agent, cred])
        await db.commit()

    auth_headers = {"Authorization": f"Bearer {plain_secret}"}

    # 2. Start Session
    sess_res = client.post("/api/v1/runtime/sessions", headers=auth_headers)
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 3. CRITICAL TEST: Denied Action leaves protected tool invocation count at ZERO
    tool_spy = MagicMock()
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=tool_spy):
        block_eval = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={
                "session_id": session_id,
                "tool": "database",
                "operation": "delete",
                "resource": "production_ledger",
                "arguments": {"account_id": "ACC-999"},
            },
            headers=auth_headers,
        )
        assert block_eval.status_code == 200
        block_data = block_eval.json()
        assert block_data["decision"] == "BLOCK"
        assert block_data["reason_code"] == "DESTRUCTIVE_OPERATION"
        assert block_data["execution_authorization"] is None

        # Attempt to execute blocked action without token
        block_exec = client.post(
            f"/api/v1/runtime/actions/{block_data['action_id']}/execute",
            json={"execution_authorization": "invalid_or_fake_token"},
            headers=auth_headers,
        )
        assert block_exec.status_code == 403

        # Assert on the protected tool directly: call count MUST be ZERO
        assert tool_spy.call_count == 0

    # 4. An allowed action must be claimed before its framework-owned tool runs.
    mock_tool = MagicMock(return_value={"result": "data retrieved", "rows": 1})
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=mock_tool):
        allow_eval = client.post(
            "/api/v1/runtime/actions/evaluate",
            json={
                "session_id": session_id,
                "tool": "safe_echo",
                "operation": "read",
                "resource": "accounts",
                "arguments": {"limit": 10},
            },
            headers=auth_headers,
        )
        assert allow_eval.status_code == 200
        allow_data = allow_eval.json()
        assert allow_data["decision"] == "ALLOW"
        exec_token = allow_data["execution_authorization"]
        assert exec_token is not None
        action_id = allow_data["action_id"]

        # Tool count before execute is 0
        assert mock_tool.call_count == 0

        # Claim allowed action. The gateway does not execute a synthetic tool.
        exec_res = client.post(
            f"/api/v1/runtime/actions/{action_id}/claim",
            json={"execution_authorization": exec_token},
            headers=auth_headers,
        )
        assert exec_res.status_code == 200
        assert exec_res.json()["status"] == "EXECUTION_CLAIMED"

        # The real runtime owns execution; gateway-side safe echo is never called.
        assert mock_tool.call_count == 0

        # 5. A second claim must be rejected before any local replay can happen.
        replay_res = client.post(
            f"/api/v1/runtime/actions/{action_id}/claim",
            json={"execution_authorization": exec_token},
            headers=auth_headers,
        )
        assert replay_res.status_code == 409
        assert mock_tool.call_count == 0

        result_res = client.post(
            f"/api/v1/runtime/actions/{action_id}/result",
            json={
                "execution_authorization": exec_token,
                "status": "succeeded",
                "output": {"result": "data retrieved", "rows": 1},
            },
            headers=auth_headers,
        )
        assert result_res.status_code == 200
        assert result_res.json()["status"] == "SUCCEEDED"

        duplicate_result = client.post(
            f"/api/v1/runtime/actions/{action_id}/result",
            json={
                "execution_authorization": exec_token,
                "status": "succeeded",
                "output": {"result": "data retrieved", "rows": 1},
            },
            headers=auth_headers,
        )
        assert duplicate_result.status_code == 200
        assert duplicate_result.json()["idempotent"] is True

    # 6. DIGEST DETERMINISM: Changed args change digest; key order does not
    eval_a = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={"session_id": session_id, "tool": "safe_echo", "operation": "read", "resource": "acc", "arguments": {"x": 1, "y": 2}},
        headers=auth_headers,
    ).json()

    eval_b = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={"session_id": session_id, "tool": "safe_echo", "operation": "read", "resource": "acc", "arguments": {"y": 2, "x": 1}},
        headers=auth_headers,
    ).json()

    eval_c = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={"session_id": session_id, "tool": "safe_echo", "operation": "read", "resource": "acc", "arguments": {"x": 1, "y": 999}},
        headers=auth_headers,
    ).json()

    assert eval_a["action_digest"] == eval_b["action_digest"], "Key order changed digest!"
    assert eval_a["action_digest"] != eval_c["action_digest"], "Argument change did not change digest!"

    # 7. SUSPENSION RE-CHECK BEFORE EXECUTION:
    # Action evaluated when active -> token issued -> agent SUSPENDED -> execute rejected!
    eval_susp = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={"session_id": session_id, "tool": "safe_echo", "operation": "read", "resource": "balances"},
        headers=auth_headers,
    ).json()
    susp_token = eval_susp["execution_authorization"]
    susp_action_id = eval_susp["action_id"]

    # Now suspend the agent in DB before execute
    async with session_maker() as db:
        await db.execute(
            AgentModel.__table__.update()
            .where(AgentModel.id == "agt_finance_gw")
            .values(status="suspended")
        )
        await db.commit()

    never_tool = MagicMock()
    with patch("agent_security.runtime.gateway.RuntimeGateway.execute_safe_echo", side_effect=never_tool):
        susp_exec = client.post(
            f"/api/v1/runtime/actions/{susp_action_id}/execute",
            json={"execution_authorization": susp_token},
            headers=auth_headers,
        )
        assert susp_exec.status_code == 403
        assert "suspended" in susp_exec.json()["error"]["message"].lower()
        assert never_tool.call_count == 0
