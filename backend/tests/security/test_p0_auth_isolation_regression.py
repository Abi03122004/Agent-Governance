"""Comprehensive Regression Test Suite for P0 Authentication, Authorization, and Tenant Isolation.

Covers:
1. Unauthenticated access is rejected (401) on all protected endpoints.
2. Authenticated users can access their authorized organizations (200).
3. Cross-tenant access is rejected (403) across all monitoring, session, audit, and agent endpoints.
4. Omitting organization_id never leaks records across tenants.
5. Forged X-User-Email headers cannot grant privileges or bypass authentication.
6. WebSocket authorization and organization scoping are strictly enforced.
"""

import asyncio
import os
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.models import (
    AgentCredentialModel,
    AgentModel,
    AgentSessionModel,
    MembershipModel,
    OrganizationModel,
    ProjectModel,
    RuntimeActionModel,
    UserModel,
)
from agent_security.db.models.runtime_activity import AuditEventModel
from agent_security.db.session import close_db, get_session_maker, init_db
from agent_security.main import create_app
from agent_security.security.authentication import create_user_token
from agent_security.security.credentials import generate_agent_credential
from agent_security.services.audit_service import AuditService
from agent_security.services.realtime import ws_manager


TEST_SECRET_KEY = "test_p0_isolation_secret_key_minimum_32_chars_12345"
TEST_DB_FILE = "test_p0_regression.db"


@pytest.fixture(scope="module")
def isolation_client():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY=TEST_SECRET_KEY,
        DATABASE_URL=f"sqlite+aiosqlite:///{TEST_DB_FILE}",
        ALLOW_DEV_HEADER_AUTH=True,
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass


@pytest.fixture(scope="module", autouse=True)
def setup_seed_data(isolation_client):
    asyncio.run(init_db())
    session_maker = get_session_maker()

    async def _seed():
        async with session_maker() as db:
            # Organizations
            org_a = OrganizationModel(id="org_alpha", name="Alpha Corp", status="active")
            org_b = OrganizationModel(id="org_beta", name="Beta Corp", status="active")
            db.add_all([org_a, org_b])

            # Projects
            proj_a = ProjectModel(id="proj_alpha", organization_id="org_alpha", name="Alpha Proj", status="active")
            proj_b = ProjectModel(id="proj_beta", organization_id="org_beta", name="Beta Proj", status="active")
            db.add_all([proj_a, proj_b])

            # Users
            user_a = UserModel(id="usr_alpha", email="alpha_user@corp.internal", display_name="Alpha User", status="active")
            user_b = UserModel(id="usr_beta", email="beta_user@corp.internal", display_name="Beta User", status="active")
            db.add_all([user_a, user_b])

            # Memberships
            mem_a = MembershipModel(id="mem_alpha", user_id="usr_alpha", organization_id="org_alpha", role="administrator")
            mem_b = MembershipModel(id="mem_beta", user_id="usr_beta", organization_id="org_beta", role="administrator")
            db.add_all([mem_a, mem_b])

            # Agents
            _, hash_a = generate_agent_credential()
            agent_a = AgentModel(
                id="agt_alpha_01",
                organization_id="org_alpha",
                project_id="proj_alpha",
                name="Agent Alpha",
                owner="alpha_user@corp.internal",
                status="active",
            )
            cred_a = AgentCredentialModel(id="cred_alpha_01", agent_id="agt_alpha_01", secret_hash=hash_a, is_active=True)
            db.add_all([agent_a, cred_a])

            _, hash_b = generate_agent_credential()
            agent_b = AgentModel(
                id="agt_beta_01",
                organization_id="org_beta",
                project_id="proj_beta",
                name="Agent Beta",
                owner="beta_user@corp.internal",
                status="active",
            )
            cred_b = AgentCredentialModel(id="cred_beta_01", agent_id="agt_beta_01", secret_hash=hash_b, is_active=True)
            db.add_all([agent_b, cred_b])

            # Sessions
            sess_a = AgentSessionModel(
                session_id="sess_alpha_01",
                organization_id="org_alpha",
                project_id="proj_alpha",
                agent_id="agt_alpha_01",
                status="active",
            )
            sess_b = AgentSessionModel(
                session_id="sess_beta_01",
                organization_id="org_beta",
                project_id="proj_beta",
                agent_id="agt_beta_01",
                status="active",
            )
            db.add_all([sess_a, sess_b])

            # Runtime Actions
            act_a = RuntimeActionModel(
                id="act_alpha_01",
                organization_id="org_alpha",
                project_id="proj_alpha",
                agent_id="agt_alpha_01",
                session_id="sess_alpha_01",
                tool="safe_echo",
                operation="read",
                resource="alpha_resource",
                normalized_action={"tool": "safe_echo", "operation": "read", "resource": "alpha_resource"},
                decision="ALLOW",
                reason_code="ALLOW_DEFAULT",
                correlation_id="corr_alpha_01",
                execution_status="EXECUTED",
                action_digest="hash_alpha",
            )
            act_b = RuntimeActionModel(
                id="act_beta_01",
                organization_id="org_beta",
                project_id="proj_beta",
                agent_id="agt_beta_01",
                session_id="sess_beta_01",
                tool="safe_echo",
                operation="read",
                resource="beta_resource",
                normalized_action={"tool": "safe_echo", "operation": "read", "resource": "beta_resource"},
                decision="BLOCK",
                reason_code="BLOCK_POLICY",
                correlation_id="corr_beta_01",
                execution_status="BLOCKED",
                action_digest="hash_beta",
            )
            db.add_all([act_a, act_b])
            await db.commit()

            # Audit events
            await AuditService.record_event(
                db, organization_id="org_alpha", project_id="proj_alpha", agent_id="agt_alpha_01",
                event_type="test.event_alpha", details={"scope": "alpha"},
            )
            await AuditService.record_event(
                db, organization_id="org_beta", project_id="proj_beta", agent_id="agt_beta_01",
                event_type="test.event_beta", details={"scope": "beta"},
            )
            await db.commit()

    asyncio.run(_seed())


# ==============================================================================
# 1. Unauthenticated Access Rejection Tests
# ==============================================================================

def test_unauthenticated_requests_are_rejected(isolation_client):
    client = isolation_client

    unauthenticated_endpoints = [
        ("GET", "/api/v1/monitoring/stats"),
        ("GET", "/api/v1/monitoring/agents"),
        ("GET", "/api/v1/monitoring/agents/agt_alpha_01"),
        ("GET", "/api/v1/monitoring/activity"),
        ("GET", "/api/v1/monitoring/policies"),
        ("GET", "/api/v1/sessions"),
        ("GET", "/api/v1/audit/events"),
        ("GET", "/api/v1/audit/verify-chain"),
        ("GET", "/api/v1/agents"),
        ("GET", "/api/v1/approvals"),
    ]

    for method, endpoint in unauthenticated_endpoints:
        if method == "GET":
            res = client.get(endpoint)
        else:
            res = client.post(endpoint)
        assert res.status_code == 401, f"Endpoint {endpoint} allowed unauthenticated access (expected 401, got {res.status_code})"


# ==============================================================================
# 2. Authenticated Access to Authorized Organization
# ==============================================================================

def test_authenticated_user_accesses_authorized_org_via_jwt(isolation_client):
    client = isolation_client
    token = create_user_token("usr_alpha", "alpha_user@corp.internal", secret_key=TEST_SECRET_KEY)
    headers = {"Authorization": f"Bearer {token}"}

    # Monitoring Stats
    res = client.get("/api/v1/monitoring/stats?organization_id=org_alpha", headers=headers)
    assert res.status_code == 200
    assert res.json()["active_agents"] >= 1

    # Monitored Agents
    res = client.get("/api/v1/monitoring/agents?organization_id=org_alpha", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert res.json()[0]["agent_id"] == "agt_alpha_01"

    # Agent Detail
    res = client.get("/api/v1/monitoring/agents/agt_alpha_01", headers=headers)
    assert res.status_code == 200
    assert res.json()["agent"]["id"] == "agt_alpha_01"

    # Runtime Activity
    res = client.get("/api/v1/monitoring/activity?organization_id=org_alpha", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Policies
    res = client.get("/api/v1/monitoring/policies", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 5

    # Sessions
    res = client.get("/api/v1/sessions?organization_id=org_alpha", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert res.json()[0]["session_id"] == "sess_alpha_01"

    # Audit Events
    res = client.get("/api/v1/audit/events?organization_id=org_alpha", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Verify Chain
    res = client.get("/api/v1/audit/verify-chain?organization_id=org_alpha", headers=headers)
    assert res.status_code == 200
    assert res.json()["verified"] is True

    # Agents List
    res = client.get("/api/v1/agents?organization_id=org_alpha", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1


# ==============================================================================
# 3. Cross-Tenant Access Rejection (Multi-Tenant Isolation)
# ==============================================================================

def test_cross_tenant_access_is_forbidden(isolation_client):
    client = isolation_client
    token_alpha = create_user_token("usr_alpha", "alpha_user@corp.internal", secret_key=TEST_SECRET_KEY)
    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}

    cross_tenant_requests = [
        ("GET", "/api/v1/monitoring/stats?organization_id=org_beta"),
        ("GET", "/api/v1/monitoring/agents?organization_id=org_beta"),
        ("GET", "/api/v1/monitoring/agents/agt_beta_01"),
        ("GET", "/api/v1/monitoring/activity?organization_id=org_beta"),
        ("GET", "/api/v1/sessions?organization_id=org_beta"),
        ("GET", "/api/v1/audit/events?organization_id=org_beta"),
        ("GET", "/api/v1/audit/verify-chain?organization_id=org_beta"),
        ("GET", "/api/v1/agents?organization_id=org_beta"),
        ("GET", "/api/v1/agents/agt_beta_01"),
        ("POST", "/api/v1/agents/agt_beta_01/credentials/cred_beta_01/revoke"),
    ]

    for method, endpoint in cross_tenant_requests:
        if method == "GET":
            res = client.get(endpoint, headers=headers_alpha)
        else:
            res = client.post(endpoint, headers=headers_alpha)
        assert res.status_code == 403, f"Cross-tenant leak! {endpoint} returned {res.status_code} instead of 403"


# ==============================================================================
# 4. Omitting organization_id Never Leaks Across Tenants
# ==============================================================================

def test_unscoped_queries_scope_only_to_authorized_tenant(isolation_client):
    client = isolation_client
    token_alpha = create_user_token("usr_alpha", "alpha_user@corp.internal", secret_key=TEST_SECRET_KEY)
    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}

    # 1. GET /agents without organization_id
    agents_res = client.get("/api/v1/agents", headers=headers_alpha)
    assert agents_res.status_code == 200
    agents = agents_res.json()
    assert all(a["organization_id"] == "org_alpha" for a in agents)
    assert not any(a["organization_id"] == "org_beta" for a in agents)

    # 2. GET /sessions without organization_id
    sessions_res = client.get("/api/v1/sessions", headers=headers_alpha)
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    assert all(s["organization_id"] == "org_alpha" for s in sessions)
    assert not any(s["organization_id"] == "org_beta" for s in sessions)

    # 3. GET /monitoring/agents without organization_id
    mon_agents_res = client.get("/api/v1/monitoring/agents", headers=headers_alpha)
    assert mon_agents_res.status_code == 200
    mon_agents = mon_agents_res.json()
    assert all(a["organization_id"] == "org_alpha" for a in mon_agents)
    assert not any(a["organization_id"] == "org_beta" for a in mon_agents)

    # 4. GET /monitoring/activity without organization_id
    act_res = client.get("/api/v1/monitoring/activity", headers=headers_alpha)
    assert act_res.status_code == 200
    activities = act_res.json()
    assert all(a["organization_id"] == "org_alpha" for a in activities)
    assert not any(a["organization_id"] == "org_beta" for a in activities)

    # 5. GET /audit/events without organization_id
    audit_res = client.get("/api/v1/audit/events", headers=headers_alpha)
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert all(e["organization_id"] == "org_alpha" for e in events)
    assert not any(e["organization_id"] == "org_beta" for e in events)


# ==============================================================================
# 5. Forged X-User-Email Header Defense
# ==============================================================================

def test_forged_x_user_email_header_cannot_escalate_privilege(isolation_client):
    client = isolation_client
    token_beta = create_user_token("usr_beta", "beta_user@corp.internal", secret_key=TEST_SECRET_KEY)

    # User Beta tries to forge X-User-Email: alpha_user@corp.internal to read Org Alpha's agent
    headers_forged = {
        "Authorization": f"Bearer {token_beta}",
        "X-User-Email": "alpha_user@corp.internal",
    }
    res = client.get("/api/v1/agents/agt_alpha_01", headers=headers_forged)
    assert res.status_code == 403, "Forged X-User-Email granted unauthorized access to Org Alpha!"


def test_production_mode_rejects_x_user_email():
    """In production environment, X-User-Email header is strictly rejected."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi import HTTPException, Request
    from sqlalchemy.ext.asyncio import AsyncSession
    from agent_security.config import get_settings
    from agent_security.middleware.auth import get_current_user

    current_settings = get_settings()
    prod_settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY="production_hardened_secret_key_minimum_32chars_long!",
        DATABASE_URL=current_settings.DATABASE_URL,
        ALLOW_DEV_HEADER_AUTH=False,
    )
    try:
        reset_settings_for_testing(prod_settings)
        req = MagicMock(spec=Request)
        req.headers = {"x-user-email": "admin@enterprise.internal"}
        mock_db = AsyncMock(spec=AsyncSession)

        async def _check():
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request=req, db=mock_db)
            assert exc_info.value.status_code == 401
            assert "Bearer token is required" in exc_info.value.detail or "required" in exc_info.value.detail.lower()

        asyncio.run(_check())
    finally:
        reset_settings_for_testing(current_settings)


# ==============================================================================
# 6. WebSocket Authentication and Scoping
# ==============================================================================

def test_websocket_rejects_unauthenticated_connection(isolation_client):
    client = isolation_client
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/monitoring/ws/activity") as ws:
            ws.receive_text()


def test_websocket_rejects_unauthorized_organization(isolation_client):
    client = isolation_client
    token_alpha = create_user_token("usr_alpha", "alpha_user@corp.internal", secret_key=TEST_SECRET_KEY)
    # User Alpha attempts to connect with organization_id=org_beta
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/monitoring/ws/activity?token={token_alpha}&organization_id=org_beta") as ws:
            ws.receive_text()


def test_websocket_receives_tenant_scoped_broadcast_only(isolation_client):
    client = isolation_client
    token_alpha = create_user_token("usr_alpha", "alpha_user@corp.internal", secret_key=TEST_SECRET_KEY)

    with client.websocket_connect(f"/api/v1/monitoring/ws/activity?token={token_alpha}&organization_id=org_alpha") as ws:
        # Broadcast event for Org Beta -> Alpha WebSocket MUST NOT receive it
        asyncio.run(ws_manager.broadcast({
            "type": "ACTION_EVALUATED",
            "organization_id": "org_beta",
            "action_id": "act_beta_secret",
        }))

        # Broadcast event for Org Alpha -> Alpha WebSocket MUST receive it
        asyncio.run(ws_manager.broadcast({
            "type": "ACTION_EVALUATED",
            "organization_id": "org_alpha",
            "action_id": "act_alpha_public",
        }))

        msg = ws.receive_json()
        assert msg["action_id"] == "act_alpha_public"
        assert msg["organization_id"] == "org_alpha"
