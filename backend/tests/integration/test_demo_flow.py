"""Full End-to-End Multi-Agent Governance Demonstration Test Flow.

Simulates the complete 8-step live demonstration:
1. Bootstrap Admin, Enterprise Organization, and Operations Project.
2. Register Finance, Support, DevOps, and Research Agents.
3. Issue high-entropy credentials and establish isolated runtime sessions.
4. Finance Agent evaluates permitted database.read -> ALLOW -> Executes with token.
5. Finance Agent attempts database.delete -> BLOCK -> Execution denied.
6. DevOps Agent attempts production deployment.update -> REQUIRE_APPROVAL -> Approver signs off.
7. Research Agent attempts forbidden secrets access -> BLOCK.
8. Finance Agent is SUSPENDED -> Action immediately halted at gateway.
9. Verify monitoring statistics, activity logs, and cryptographic audit hash chain integrity.
"""

import asyncio
import pytest
from fastapi.testclient import TestClient

from agent_security.config import Settings, reset_settings_for_testing
from agent_security.db.session import close_db, init_db
from agent_security.main import create_app


@pytest.fixture(scope="module")
def app_client():
    asyncio.run(close_db())
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_secret_key_minimum_32_characters_long_123",
        DATABASE_URL="sqlite+aiosqlite:///file:memdb_demo_flow?mode=memory&cache=shared&uri=true",
    )
    reset_settings_for_testing(test_settings)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client
    asyncio.run(close_db())
    reset_settings_for_testing(None)


@pytest.mark.asyncio
async def test_full_agent_governance_demo_flow(app_client):
    client = app_client
    await init_db()

    admin_headers = {"X-User-Email": "security_admin@enterprise.internal"}
    reviewer_headers = {"X-User-Email": "reviewer@enterprise.internal"}

    # -------------------------------------------------------------
    # Step 1: Bootstrap Identity & Tenancy
    # -------------------------------------------------------------
    # 1. Create Admin User
    u_resp = client.post("/api/v1/users", json={
        "id": "usr_admin",
        "email": "security_admin@enterprise.internal",
        "display_name": "Security Officer",
    })
    assert u_resp.status_code in (201, 200)

    # 2. Create Reviewer User (for requester-approver separation)
    u2_resp = client.post("/api/v1/users", json={
        "id": "usr_reviewer",
        "email": "reviewer@enterprise.internal",
        "display_name": "Senior Reviewer",
    })
    assert u2_resp.status_code in (201, 200)

    # 3. Create Organization
    o_resp = client.post("/api/v1/organizations", json={
        "id": "org_enterprise",
        "name": "Enterprise Autonomous Fleet",
    })
    assert o_resp.status_code in (201, 200)

    # 4. Create Admin Membership
    m_resp = client.post("/api/v1/users/memberships", json={
        "id": "mem_admin_01",
        "user_id": "usr_admin",
        "organization_id": "org_enterprise",
        "role": "administrator",
    })
    assert m_resp.status_code in (201, 200)

    # 5. Create Reviewer Membership (approver role in org)
    m2_resp = client.post("/api/v1/users/memberships", json={
        "id": "mem_reviewer_01",
        "user_id": "usr_reviewer",
        "organization_id": "org_enterprise",
        "role": "approver",
    })
    assert m2_resp.status_code in (201, 200)

    # 6. Create Operations Project
    p_resp = client.post("/api/v1/projects", json={
        "id": "proj_operations",
        "organization_id": "org_enterprise",
        "name": "Core Ops",
    })
    assert p_resp.status_code in (201, 200)

    # -------------------------------------------------------------
    # Step 2: Register 4 Autonomous Agents and Issue Credentials
    # -------------------------------------------------------------
    agents_manifest = {
        "finance_agent": ("Finance Agent", "Automated ledger reconciliation"),
        "support_agent": ("Support Agent", "Customer ticket analysis"),
        "devops_agent": ("DevOps Agent", "Cluster management and continuous delivery"),
        "research_agent": ("Research Agent", "Market intelligence literature review"),
    }

    credentials = {}
    for agent_id, (name, purpose) in agents_manifest.items():
        # Register agent
        reg_resp = client.post("/api/v1/agents", headers=admin_headers, json={
            "id": agent_id,
            "organization_id": "org_enterprise",
            "project_id": "proj_operations",
            "name": name,
            "environment": "production",
            "purpose": purpose,
        })
        assert reg_resp.status_code == 201

        # Issue credential
        cred_resp = client.post(f"/api/v1/agents/{agent_id}/credentials", headers=admin_headers)
        assert cred_resp.status_code == 201
        credentials[agent_id] = cred_resp.json()["plaintext_secret"]

    # -------------------------------------------------------------
    # Step 3: Establish Isolated Runtime Sessions
    # -------------------------------------------------------------
    sessions = {}
    for agent_id in agents_manifest:
        token = credentials[agent_id]
        sess_resp = client.post(
            "/api/v1/runtime/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert sess_resp.status_code == 201
        sessions[agent_id] = sess_resp.json()["session_id"]

    # -------------------------------------------------------------
    # Step 4: Finance Agent -> database.read -> ALLOW -> Execution
    # -------------------------------------------------------------
    fin_headers = {"Authorization": f"Bearer {credentials['finance_agent']}"}
    eval_read = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=fin_headers,
        json={
            "session_id": sessions["finance_agent"],
            "tool": "safe_echo",
            "operation": "read",
            "resource": "ledger_transactions",
            "arguments": {"month": "2026-09"},
            "purpose": "Monthly compliance report",
        },
    )
    assert eval_read.status_code == 200
    read_data = eval_read.json()
    assert read_data["decision"] == "ALLOW"
    assert read_data["execution_authorization"] is not None

    # Execute allowed action
    exec_read = client.post(
        f"/api/v1/runtime/actions/{read_data['action_id']}/execute",
        headers=fin_headers,
        json={"execution_authorization": read_data["execution_authorization"]},
    )
    assert exec_read.status_code == 200
    assert exec_read.json()["status"] == "EXECUTED"

    # -------------------------------------------------------------
    # Step 5: Finance Agent -> database.delete -> BLOCK -> No Token
    # -------------------------------------------------------------
    eval_del = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=fin_headers,
        json={
            "session_id": sessions["finance_agent"],
            "tool": "database",
            "operation": "delete",
            "resource": "ledger_transactions",
            "arguments": {"all": True},
            "purpose": "Purge ledger history",
        },
    )
    assert eval_del.status_code == 200
    del_data = eval_del.json()
    assert del_data["decision"] == "BLOCK"
    assert del_data["reason_code"] == "DESTRUCTIVE_OPERATION"
    assert del_data["execution_authorization"] is None

    # -------------------------------------------------------------
    # Step 6: DevOps Agent -> deployment.update -> REQUIRE_APPROVAL
    # -------------------------------------------------------------
    devops_headers = {"Authorization": f"Bearer {credentials['devops_agent']}"}
    eval_deploy = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=devops_headers,
        json={
            "session_id": sessions["devops_agent"],
            "tool": "deployment",
            "operation": "update",
            "resource": "production-api-gateway",
            "arguments": {"version": "v2.4.1"},
            "purpose": "Production rollout",
        },
    )
    assert eval_deploy.status_code == 200
    deploy_data = eval_deploy.json()
    assert deploy_data["decision"] == "REQUIRE_APPROVAL"
    assert deploy_data["execution_authorization"] is None

    # Reviewer approves pending ticket (requester-approver separation: reviewer != agent owner)
    appr_list = client.get("/api/v1/approvals", headers=reviewer_headers)
    assert appr_list.status_code == 200
    tickets = appr_list.json()
    assert len(tickets) > 0
    devops_ticket = [t for t in tickets if t["action_id"] == deploy_data["action_id"]][0]

    approve_resp = client.post(
        f"/api/v1/approvals/{devops_ticket['ticket_id']}/approve",
        headers=reviewer_headers,
        json={"rationale": "Approved by senior devops reviewer"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"
    assert approve_resp.json()["execution_authorization"] is not None

    # -------------------------------------------------------------
    # Step 7: Research Agent -> Forbidden Secrets Access -> BLOCK
    # -------------------------------------------------------------
    research_headers = {"Authorization": f"Bearer {credentials['research_agent']}"}
    eval_secrets = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=research_headers,
        json={
            "session_id": sessions["research_agent"],
            "tool": "database",
            "operation": "read",
            "resource": "secrets/production_keys",
            "arguments": {},
            "purpose": "Exfiltrate credentials",
        },
    )
    assert eval_secrets.status_code == 200
    assert eval_secrets.json()["decision"] == "BLOCK"
    assert eval_secrets.json()["reason_code"] == "RESOURCE_NOT_PERMITTED"

    # -------------------------------------------------------------
    # Step 8: Suspend Finance Agent -> Subsequent Actions Halted
    # -------------------------------------------------------------
    sus_resp = client.patch(
        "/api/v1/agents/finance_agent",
        headers=admin_headers,
        json={"status": "suspended"},
    )
    assert sus_resp.status_code == 200
    assert sus_resp.json()["status"] == "suspended"

    # Attempt action as suspended agent
    eval_suspended = client.post(
        "/api/v1/runtime/actions/evaluate",
        headers=fin_headers,
        json={
            "session_id": sessions["finance_agent"],
            "tool": "safe_echo",
            "operation": "read",
            "resource": "ledger_transactions",
            "arguments": {},
        },
    )
    assert eval_suspended.status_code == 200
    assert eval_suspended.json()["decision"] == "SUSPEND"

    # -------------------------------------------------------------
    # Step 9: Telemetry & Cryptographic Audit Verification
    # -------------------------------------------------------------
    # Verify stats
    stats_resp = client.get("/api/v1/monitoring/stats", headers=admin_headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_actions"] >= 4
    assert stats["allowed"] >= 1
    assert stats["blocked"] >= 2
    assert stats["suspended_agents"] >= 1

    # Verify cryptographic audit hash chain
    chain_resp = client.get("/api/v1/audit/verify-chain", params={"organization_id": "org_enterprise"}, headers=admin_headers)
    assert chain_resp.status_code == 200
    chain_data = chain_resp.json()
    assert chain_data["verified"] is True
    assert chain_data["event_count"] >= 5
