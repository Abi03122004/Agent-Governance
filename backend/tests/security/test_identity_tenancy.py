"""Tests for Phase 1: Identity, Tenancy, and Negative Authentication."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.config import Settings
from agent_security.db.models import (
    AgentCredentialModel,
    AgentModel,
    AgentSessionModel,
    OrganizationModel,
    ProjectModel,
    UserModel,
    MembershipModel,
)
from agent_security.db.session import get_session_maker, init_db
from agent_security.main import create_app
from agent_security.security.credentials import generate_agent_credential, hash_secret


@pytest.fixture(scope="module")
def app_and_client():
    from agent_security.config import reset_settings_for_testing
    from agent_security.db.session import close_db
    import asyncio
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_secret_key_minimum_32_characters_long_123",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_id?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.asyncio
async def test_identity_and_tenancy_matrix(app_and_client):
    client = app_and_client
    await init_db()
    session_maker = get_session_maker()

    now = datetime.now(timezone.utc)

    # 1. Setup Org A and Org B
    async with session_maker() as db:
        org_a = OrganizationModel(id="org_alpha", name="Alpha Corp", status="active")
        org_b = OrganizationModel(id="org_beta", name="Beta Corp", status="active")
        db.add_all([org_a, org_b])

        proj_a = ProjectModel(id="proj_alpha_main", organization_id="org_alpha", name="Alpha Main")
        proj_b = ProjectModel(id="proj_beta_main", organization_id="org_beta", name="Beta Main")
        db.add_all([proj_a, proj_b])

        # Active agent in Org A
        plain_a, hash_a = generate_agent_credential()
        agent_a = AgentModel(id="agt_alpha_01", organization_id="org_alpha", project_id="proj_alpha_main", name="Alpha Agent", owner="admin@corp.internal", status="active")
        cred_a = AgentCredentialModel(id="cred_alpha_01", agent_id="agt_alpha_01", secret_hash=hash_a, is_active=True)
        db.add_all([agent_a, cred_a])

        # Expired credential agent
        plain_exp, hash_exp = generate_agent_credential()
        agent_exp = AgentModel(id="agt_exp_01", organization_id="org_alpha", project_id="proj_alpha_main", name="Expired Agent", owner="admin@corp.internal", status="active")
        cred_exp = AgentCredentialModel(
            id="cred_exp_01", agent_id="agt_exp_01", secret_hash=hash_exp, is_active=True,
            expires_at=now - timedelta(minutes=10)
        )
        db.add_all([agent_exp, cred_exp])

        # Revoked credential agent
        plain_rev, hash_rev = generate_agent_credential()
        agent_rev = AgentModel(id="agt_rev_01", organization_id="org_alpha", project_id="proj_alpha_main", name="Revoked Cred Agent", owner="admin@corp.internal", status="active")
        cred_rev = AgentCredentialModel(
            id="cred_rev_01", agent_id="agt_rev_01", secret_hash=hash_rev, is_active=False,
            revoked_at=now - timedelta(minutes=5)
        )
        db.add_all([agent_rev, cred_rev])

        # Suspended agent
        plain_susp, hash_susp = generate_agent_credential()
        agent_susp = AgentModel(id="agt_susp_01", organization_id="org_alpha", project_id="proj_alpha_main", name="Suspended Agent", owner="admin@corp.internal", status="suspended")
        cred_susp = AgentCredentialModel(id="cred_susp_01", agent_id="agt_susp_01", secret_hash=hash_susp, is_active=True)
        db.add_all([agent_susp, cred_susp])

        # Revoked agent
        plain_rev_agent, hash_rev_agent = generate_agent_credential()
        agent_rev_agent = AgentModel(id="agt_rev_agent_01", organization_id="org_alpha", project_id="proj_alpha_main", name="Revoked Agent", owner="admin@corp.internal", status="revoked")
        cred_rev_agent = AgentCredentialModel(id="cred_rev_agent_01", agent_id="agt_rev_agent_01", secret_hash=hash_rev_agent, is_active=True)
        db.add_all([agent_rev_agent, cred_rev_agent])

        # Active agent in Org B
        plain_b, hash_b = generate_agent_credential()
        agent_b = AgentModel(id="agt_beta_01", organization_id="org_beta", project_id="proj_beta_main", name="Beta Agent", owner="admin@corp.internal", status="active")
        cred_b = AgentCredentialModel(id="cred_beta_01", agent_id="agt_beta_01", secret_hash=hash_b, is_active=True)
        db.add_all([agent_b, cred_b])

        # User for admin ops
        user_admin = UserModel(id="usr_admin_01", email="admin@corp.internal", display_name="Admin", status="active")
        db.add(user_admin)
        mem_a = MembershipModel(id="mem_a_01", user_id="usr_admin_01", organization_id="org_alpha", role="administrator")
        db.add(mem_a)

        await db.commit()

    def get_err(resp):
        d = resp.json()
        if "error" in d and "message" in d["error"]:
            return d["error"]["message"]
        return d.get("detail", "")

    # --- NEGATIVE TEST: Invalid bearer credential
    res = client.post("/api/v1/runtime/sessions", headers={"Authorization": "Bearer agt_invalid_secret_token"})
    assert res.status_code == 401
    assert get_err(res) == "Invalid agent credentials"

    # --- NEGATIVE TEST: Expired credential
    res = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {plain_exp}"})
    assert res.status_code == 401
    assert get_err(res) == "Invalid agent credentials"

    # --- NEGATIVE TEST: Revoked credential
    res = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {plain_rev}"})
    assert res.status_code == 401
    assert get_err(res) == "Invalid agent credentials"

    # --- NEGATIVE TEST: Revoked agent
    res = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {plain_rev_agent}"})
    assert res.status_code == 401
    assert get_err(res) == "Invalid agent credentials"

    # --- NEGATIVE TEST: Suspended agent cannot start runtime session
    res = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {plain_susp}"})
    assert res.status_code == 403
    assert "Suspended agent cannot start runtime session" in get_err(res)

    # --- POSITIVE TEST: Active Agent A starts session
    res_a = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {plain_a}"})
    assert res_a.status_code == 201
    sess_a_id = res_a.json()["session_id"]
    assert res_a.json()["organization_id"] == "org_alpha"
    assert res_a.json()["agent_id"] == "agt_alpha_01"

    # --- POSITIVE TEST: Active Agent B starts session
    res_b = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {plain_b}"})
    assert res_b.status_code == 201
    sess_b_id = res_b.json()["session_id"]
    assert res_b.json()["organization_id"] == "org_beta"
    assert res_b.json()["agent_id"] == "agt_beta_01"

    # --- NEGATIVE TEST: Cross-tenant session hijacking
    # Agent B attempts to evaluate an action using Agent A's session in Org A
    cross_action = {
        "session_id": sess_a_id,
        "tool": "safe_echo",
        "operation": "read",
        "resource": "ledger",
    }
    res_cross = client.post(
        "/api/v1/runtime/actions/evaluate",
        json=cross_action,
        headers={"Authorization": f"Bearer {plain_b}"},
    )
    # Must be rejected because session is not owned by Agent B
    assert res_cross.status_code == 404
    assert "Active session not found" in get_err(res_cross)

    # --- NEGATIVE TEST: Expired session cannot evaluate actions
    # Create an expired session for Agent A
    res_exp_sess = client.post(
        "/api/v1/runtime/sessions?expires_in_seconds=1",
        headers={"Authorization": f"Bearer {plain_a}"},
    )
    assert res_exp_sess.status_code == 201
    exp_sess_id = res_exp_sess.json()["session_id"]

    # Manually expire the session in DB
    async with session_maker() as db:
        row = (await db.execute(
            AgentSessionModel.__table__.update()
            .where(AgentSessionModel.session_id == exp_sess_id)
            .values(expires_at=now - timedelta(minutes=1))
        ))
        await db.commit()

    res_action_exp = client.post(
        "/api/v1/runtime/actions/evaluate",
        json={"session_id": exp_sess_id, "tool": "safe_echo", "operation": "read", "resource": "ledger"},
        headers={"Authorization": f"Bearer {plain_a}"},
    )
    assert res_action_exp.status_code == 403
    assert "Session expired" in get_err(res_action_exp)

    # --- CREDENTIAL ROTATION TEST
    rot_res = client.post(
        "/api/v1/agents/agt_alpha_01/credentials/rotate",
        headers={"X-User-Email": "admin@corp.internal"},
    )
    assert rot_res.status_code == 201
    new_plain_a = rot_res.json()["plaintext_secret"]
    assert new_plain_a != plain_a

    # Old credential now fails
    old_res = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {plain_a}"})
    assert old_res.status_code == 401

    # New credential succeeds
    new_sess_res = client.post("/api/v1/runtime/sessions", headers={"Authorization": f"Bearer {new_plain_a}"})
    assert new_sess_res.status_code == 201
