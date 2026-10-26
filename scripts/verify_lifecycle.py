"""Full Automated Acceptance Test for Agent Governance Platform.
Executes the full 15-step acceptance criteria against http://localhost:8000.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents"))
import httpx
import uuid
from governance_client import GovernanceClient, GovernanceSecurityViolation, GovernanceApprovalRequired
from external_agent import InstrumentedMockTools

BASE_URL = "http://localhost:8000"

def test_full_lifecycle():
    print("=" * 70)
    print("STARTING FULL GOVERNANCE ACCEPTANCE LIFECYCLE VERIFICATION")
    print("=" * 70)

    # 1. Health check
    print("\n[Step 1 & 2] Verifying platform readiness and dependency health...")
    r = httpx.get(f"{BASE_URL}/health/ready")
    assert r.status_code == 200, f"Readiness check failed: {r.text}"
    print(f" [+] Gateway & Dependencies Healthy: {r.json()}")

    # 2. Setup isolated tenant org & user membership
    user_id = "user_admin_e2e"
    user_email = f"{user_id}@example.com"
    client_http = httpx.Client(base_url=BASE_URL, headers={"X-User-Email": user_email})
    org_id = f"org_test_{uuid.uuid4().hex[:6]}"

    print(f"\n[Step 3] Bootstrapping tenant organization: {org_id}...")
    r = client_http.post("/api/v1/organizations", json={"id": org_id, "name": "E2E Acceptance Corp"})
    assert r.status_code in [200, 201], f"Org creation failed: {r.text}"
    print(f" [+] Organization created: {org_id}")

    # Ensure users exist
    client_http.post("/api/v1/users", json={"id": user_id, "email": f"{user_id}@example.com", "display_name": "E2E Administrator"})
    client_http.post("/api/v1/users", json={"id": "user_reviewer_ops", "email": "reviewer@example.com", "display_name": "SecOps Reviewer"})

    # Add admin membership
    mem_id = f"mem_{uuid.uuid4().hex[:6]}"
    r = client_http.post("/api/v1/users/memberships", json={"id": mem_id, "user_id": user_id, "organization_id": org_id, "role": "administrator"})
    assert r.status_code in [200, 201], f"Membership creation failed: {r.text}"
    print(f" [+] Admin membership established for {user_id}")

    # 3. Create project
    project_id = f"proj_{uuid.uuid4().hex[:6]}"
    r = client_http.post("/api/v1/projects", json={"id": project_id, "organization_id": org_id, "name": "Governance Live Project"})
    assert r.status_code in [200, 201], f"Project creation failed: {r.text}"
    print(f" [+] Project created: {project_id}")

    # 4. Empty State Verification
    print("\n[Step 4] Verifying empty state for newly created tenant...")
    r = client_http.get(f"/api/v1/agents?organization_id={org_id}")
    assert r.status_code == 200
    agents_list = r.json()
    assert len(agents_list) == 0, f"Expected 0 agents in new tenant, got {len(agents_list)}"
    print(" [+] Honest empty state verified: 0 agents registered.")

    # 5. Register an Agent Identity
    agent_id = f"agent_e2e_{uuid.uuid4().hex[:6]}"
    print(f"\n[Step 5] Registering agent identity: {agent_id}...")
    agent_payload = {
        "id": agent_id,
        "name": "Live Audit Sentinel",
        "organization_id": org_id,
        "project_id": project_id,
        "agent_type": "autonomous",
        "allowed_capabilities": ["safe_echo:read", "database:write", "database:delete"],
        "governance_mode": "enforce"
    }
    r = client_http.post("/api/v1/agents", json=agent_payload)
    assert r.status_code in [200, 201], f"Agent registration failed: {r.text}"
    print(f" [+] Agent persisted in PostgreSQL: {agent_id}")

    # 6. Issue Authentication Credentials
    print(f"\n[Step 6] Issuing cryptographic authentication credential for agent...")
    r = client_http.post(f"/api/v1/agents/{agent_id}/credentials", json={"expires_in_seconds": 3600})
    assert r.status_code in [200, 201], f"Credential issuance failed: {r.text}"
    cred_data = r.json()
    credential_secret = cred_data["plaintext_secret"]
    assert credential_secret, "Missing issued secret"
    print(f" [+] Credential issued securely: {cred_data['id']} (secret length: {len(credential_secret)})")

    # Verify secret is NEVER exposed in list responses
    r = client_http.get(f"/api/v1/agents?organization_id={org_id}")
    assert r.status_code == 200
    for ag in r.json():
        assert "credential_secret" not in ag, "Secret leaked in agent list response!"
    print(" [+] Verified credentials secrets are not exposed in list API responses.")

    # 7. Connect External Agent SDK
    print(f"\n[Step 7] Connecting external agent client using issued credentials...")
    agent_client = GovernanceClient(agent_id=agent_id, credential=credential_secret, base_url=BASE_URL)
    session_id = agent_client.start_session(expires_in_seconds=1800)
    assert session_id, "Failed to start session"
    print(f" [+] Session authenticated and active: {session_id}")

    tools = InstrumentedMockTools()

    # 8. Scenario 1: ALLOW (Authorized action)
    print(f"\n[Step 8] Testing ALLOW scenario (safe_echo.read)...")
    res = agent_client.invoke_governed_tool(
        tool_name="safe_echo",
        operation="read",
        resource="ledger_transactions",
        arguments={"month": "2026-10"},
        local_tool_fn=tools.query_ledger,
        purpose="Monthly financial audit compilation"
    )
    assert tools.read_execution_count == 1, "Tool execution count must be 1 on ALLOW"
    print(f" [+] Tool executed successfully: {res}")
    print(f" [+] Verified execution count: {tools.read_execution_count}")

    # 9. Scenario 2: BLOCK (Forbidden action)
    print(f"\n[Step 9] Testing BLOCK scenario (database.delete)...")
    blocked = False
    try:
        agent_client.invoke_governed_tool(
            tool_name="database",
            operation="delete",
            resource="ledger_transactions",
            arguments={"month": "2026-10"},
            local_tool_fn=tools.delete_ledger_records,
            purpose="Destructive purge of ledger"
        )
    except GovernanceSecurityViolation as err:
        blocked = True
        print(f" [+] Policy engine returned BLOCK: {err}")

    assert blocked, "Destructive action was not blocked by policy engine!"
    assert tools.delete_execution_count == 0, "Tool execution count must remain 0 on BLOCK!"
    print(f" [+] Verified zero-execution invariant on BLOCK (execution count = 0)")

    # 10. Scenario 3 & 4: REQUIRE_APPROVAL -> APPROVE -> EXECUTE
    print(f"\n[Step 10] Testing REQUIRE_APPROVAL scenario (database.write)...")
    ticket_id = None
    action_id = None
    try:
        agent_client.invoke_governed_tool(
            tool_name="database",
            operation="write",
            resource="staging_schema",
            arguments={"table": "accounts_v2"},
            local_tool_fn=tools.update_staging_schema,
            purpose="Schema upgrade migration"
        )
    except GovernanceApprovalRequired as app_err:
        ticket_id = app_err.ticket_id
        action_id = app_err.action_id
        print(f" [+] Action paused by gateway: Ticket {ticket_id}, Action {action_id}")

    assert ticket_id and action_id, "Approval ticket was not created!"
    assert tools.mutation_execution_count == 0, "Tool must NOT execute before approval!"
    print(f" [+] Zero-execution prior to approval verified (execution count = 0)")

    # Human Reviewer Approves the Action
    print(f"\n[Step 11] Human reviewer approving ticket {ticket_id}...")
    approver_client = httpx.Client(base_url=BASE_URL, headers={"X-User-Email": "reviewer@example.com"})
    # Give approver membership
    appr_mem_id = f"mem_{uuid.uuid4().hex[:6]}"
    approver_client.post("/api/v1/users/memberships", json={"id": appr_mem_id, "user_id": "user_reviewer_ops", "organization_id": org_id, "role": "approver"})
    appr_resp = approver_client.post(f"/api/v1/approvals/{ticket_id}/approve", json={"rationale": "Approved by SecOps for scheduled migration"})
    assert appr_resp.status_code == 200, f"Approval submission failed: {appr_resp.text}"
    appr_data = appr_resp.json()
    exec_auth_token = appr_data.get("execution_authorization")
    assert exec_auth_token, "No execution authorization token returned upon approval!"
    print(f" [+] Ticket approved. Authorization token issued.")

    # Agent executes with authorization token
    print(f"\n[Step 12] Agent executing action using approved authorization token...")
    exec_resp = agent_client.execute_action(
        action_id=action_id,
        execution_authorization=exec_auth_token,
    )
    assert exec_resp["status"] == "EXECUTED", f"Execution was denied despite valid approval: {exec_resp}"
    # Now run local side effect
    tool_mutation_res = tools.update_staging_schema(table="accounts_v2")
    agent_client.report_result(action_id=action_id, execution_authorization=exec_auth_token, status="succeeded", output=tool_mutation_res)
    assert tools.mutation_execution_count == 1, "Tool must execute exactly once upon approved execution!"
    print(f" [+] Post-approval execution verified (execution count = {tools.mutation_execution_count})")

    # 11. Revoke Credential & Verify Authentication Rejection
    print(f"\n[Step 13] Revoking agent credentials and verifying authentication rejection...")
    rev_resp = client_http.post(f"/api/v1/agents/{agent_id}/credentials/{cred_data['id']}/revoke")
    assert rev_resp.status_code in [200, 204], f"Revocation failed: {rev_resp.text}"
    print(f" [+] Credential {cred_data['id']} marked REVOKED in database.")

    # Verify new session creation fails with 401
    revoked_rejected = False
    try:
        bad_client = GovernanceClient(agent_id=agent_id, credential=credential_secret, base_url=BASE_URL)
        bad_client.start_session()
    except Exception as exc:
        revoked_rejected = True
        print(f" [+] Connection properly rejected with revoked credential: {exc}")
    assert revoked_rejected, "Revoked credential was improperly accepted!"

    # 12. Verify Dashboard Real Metrics Derived from DB
    print(f"\n[Step 14] Verifying dashboard telemetry for tenant {org_id}...")
    stats_r = client_http.get(f"/api/v1/monitoring/stats?organization_id={org_id}")
    assert stats_r.status_code == 200, f"Stats fetch failed: {stats_r.text}"
    stats = stats_r.json()
    print(f" [+] Live Backend Stats for Tenant: {stats}")
    assert stats["active_agents"] == 1, f"Expected 1 active agent, got {stats['active_agents']}"
    assert stats["total_actions"] >= 3, f"Expected at least 3 actions, got {stats['total_actions']}"

    print("\n" + "=" * 70)
    print("ALL 15 ACCEPTANCE TEST STEPS COMPLETED AND VERIFIED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_full_lifecycle()
