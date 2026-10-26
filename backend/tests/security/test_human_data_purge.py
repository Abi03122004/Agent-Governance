"""Security verification for Human-Only Data Deletion & Purge Controls."""

import asyncio
import pytest
from fastapi.testclient import TestClient

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.session import close_db, get_session_maker, init_db
from agent_security.main import create_app
from agent_security.db.models import (
    OrganizationModel,
    ProjectModel,
    UserModel,
    MembershipModel,
    AgentModel,
    AgentCredentialModel,
)


@pytest.fixture(scope="module")
def purge_client():
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_human_purge_secret_key_32chars_long",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_purge?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.anyio
async def test_human_delete_agent_and_purge_endpoints(purge_client):
    client = purge_client
    await init_db()
    session_maker = get_session_maker()

    async with session_maker() as db:
        org = OrganizationModel(id="org_purge_test", name="Purge Test Org")
        proj = ProjectModel(id="proj_purge_test", organization_id="org_purge_test", name="Purge Test Project")
        user = UserModel(id="usr_human_admin", email="operator@human.corp", display_name="Human Operator")
        membership = MembershipModel(id="mem_purge_admin", user_id="usr_human_admin", organization_id="org_purge_test", role="admin")
        agent = AgentModel(
            id="agent_to_delete",
            organization_id="org_purge_test",
            project_id="proj_purge_test",
            name="Doomed Agent",
            owner="operator@human.corp",
            status="active",
        )
        cred = AgentCredentialModel(
            id="cred_doomed",
            agent_id="agent_to_delete",
            secret_hash="hash_dummy",
            is_active=True,
        )
        db.add_all([org, proj, user, membership, agent, cred])
        await db.commit()

    headers = {"X-User-Email": "operator@human.corp"}

    # 1. Delete agent via human operator
    res = client.delete("/api/v1/agents/agent_to_delete", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "deleted"
    assert data["agent_id"] == "agent_to_delete"

    # Verify agent no longer exists
    res_get = client.get("/api/v1/agents/agent_to_delete", headers=headers)
    assert res_get.status_code == 404

    # 2. Clear Audit Events requires "CONFIRM"
    res_unconfirmed = client.post(
        "/api/v1/audit/clear",
        headers=headers,
        json={"confirmation": "INVALID"},
    )
    assert res_unconfirmed.status_code == 400

    res_audit_clear = client.post(
        "/api/v1/audit/clear",
        headers=headers,
        json={"confirmation": "CONFIRM", "rationale": "Test Reset"},
    )
    assert res_audit_clear.status_code == 200
    assert res_audit_clear.json()["status"] == "cleared"

    # 3. Clear Runtime Activity requires "CONFIRM"
    res_act_unconfirmed = client.post(
        "/api/v1/monitoring/activity/clear",
        headers=headers,
        json={"confirmation": "WRONG"},
    )
    assert res_act_unconfirmed.status_code == 400

    res_act_clear = client.post(
        "/api/v1/monitoring/activity/clear",
        headers=headers,
        json={"confirmation": "CONFIRM"},
    )
    assert res_act_clear.status_code == 200
    assert res_act_clear.json()["status"] == "cleared"

    # 4. Clear Sessions requires "CONFIRM"
    res_sess_clear = client.post(
        "/api/v1/sessions/clear?confirmation=CONFIRM",
        headers=headers,
    )
    assert res_sess_clear.status_code == 200
    assert res_sess_clear.json()["status"] == "cleared"
