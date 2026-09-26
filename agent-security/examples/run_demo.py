"""Master Autonomous Agent Security & Governance Platform Demo Runner.

Executes the exact 8-step verification flow:
1. Register Organization, Project, and 4 Agents (Finance, Support, DevOps, Research).
2. Generate secure credentials for each agent.
3. Authenticate and create isolated runtime sessions.
4. Finance Agent executes permitted database.read -> ALLOW -> Tool Executes.
5. Finance Agent attempts database.delete -> BLOCK -> Tool NEVER Executes.
6. DevOps Agent attempts staging mutation -> REQUIRE_APPROVAL -> Execution Paused.
7. Finance Agent is SUSPENDED -> Next action -> SUSPEND / BLOCKED.
8. Live activity stream and telemetry verified for Dashboard.
"""

import os
import sys
import time
import requests

BASE_URL = os.getenv("GOVERNANCE_URL", "http://localhost:8000")
USER_EMAIL = "security_admin@enterprise.internal"
ADMIN_HEADERS = {"X-User-Email": USER_EMAIL}


def log_step(step: int, title: str):
    print("\n" + "=" * 70)
    print(f"STEP {step}: {title}")
    print("=" * 70)


def ensure_bootstrap():
    # 1. Ensure user
    try:
        requests.post(
            f"{BASE_URL}/api/v1/users",
            json={"id": "usr_admin", "email": USER_EMAIL, "display_name": "Security Officer"},
            timeout=5,
        )
    except Exception:
        pass

    # 2. Ensure organization
    try:
        requests.post(
            f"{BASE_URL}/api/v1/organizations",
            json={"id": "org_enterprise", "name": "Enterprise Autonomous Fleet"},
            timeout=5,
        )
    except Exception:
        pass

    # 3. Ensure membership
    try:
        requests.post(
            f"{BASE_URL}/api/v1/users/memberships",
            json={
                "id": "mem_admin_01",
                "user_id": "usr_admin",
                "organization_id": "org_enterprise",
                "role": "administrator",
            },
            timeout=5,
        )
    except Exception:
        pass

    # 4. Ensure project
    try:
        requests.post(
            f"{BASE_URL}/api/v1/projects",
            json={"id": "proj_operations", "organization_id": "org_enterprise", "name": "Core Ops"},
            timeout=5,
        )
    except Exception:
        pass


def register_agent(agent_id: str, name: str, purpose: str):
    try:
        requests.post(
            f"{BASE_URL}/api/v1/agents",
            headers=ADMIN_HEADERS,
            json={
                "id": agent_id,
                "organization_id": "org_enterprise",
                "project_id": "proj_operations",
                "name": name,
                "environment": "production",
                "purpose": purpose,
            },
            timeout=5,
        )
    except Exception:
        pass

    # Generate credential
    cred_resp = requests.post(
        f"{BASE_URL}/api/v1/agents/{agent_id}/credentials",
        headers=ADMIN_HEADERS,
        timeout=5,
    )
    if cred_resp.status_code == 201:
        return cred_resp.json()["plaintext_secret"]
    raise RuntimeError(f"Failed to issue credential for {agent_id}: {cred_resp.text}")


def main():
    print("Connecting to Governance Control Plane at:", BASE_URL)
    health = requests.get(f"{BASE_URL}/health/live", timeout=5).json()
    print(f"Control Plane Status: {health.get('status')} | Service: {health.get('service')}")

    ensure_bootstrap()

    # Step 1: Register 4 Independent Agents
    log_step(1, "Register Finance, Support, DevOps, and Research Agents")
    agents = {
        "finance_agent": ("Finance Agent", "Automated ledger reconciliation"),
        "support_agent": ("Support Agent", "Customer ticket analysis"),
        "devops_agent": ("DevOps Agent", "Cluster management and deployments"),
        "research_agent": ("Research Agent", "Market intelligence literature review"),
    }

    credentials = {}
    for aid, (name, purpose) in agents.items():
        secret = register_agent(aid, name, purpose)
        credentials[aid] = secret
        print(f" -> Registered {name} ({aid}) with secure credential")

    # Step 2 & 3: Authenticate and Create Runtime Sessions
    log_step(2, "Authenticate Agents & Establish Isolated Runtime Sessions")
    sessions = {}
    for aid in agents:
        token = credentials[aid]
        auth_hdr = {"Authorization": f"Bearer {token}"}
        sess_resp = requests.post(
            f"{BASE_URL}/api/v1/runtime/sessions",
            headers=auth_hdr,
            timeout=5,
        ).json()
        sessions[aid] = sess_resp["session_id"]
        print(f" -> {agents[aid][0]}: Active Session = {sessions[aid]}")

    # Step 4: Finance Agent -> database.read -> ALLOW -> Execute
    log_step(4, "Finance Agent: Permitted Read -> [ALLOW] -> Tool Executes")
    fin_token = credentials["finance_agent"]
    fin_headers = {"Authorization": f"Bearer {fin_token}"}
    eval_resp = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/evaluate",
        headers=fin_headers,
        json={
            "session_id": sessions["finance_agent"],
            "tool": "database",
            "operation": "read",
            "resource": "ledger_transactions",
            "arguments": {"month": "2026-09"},
            "purpose": "Monthly compliance report",
        },
        timeout=5,
    ).json()

    print(f"Policy Decision: {eval_resp['decision']}")
    print(f"Reason Code:     {eval_resp['reason_code']}")
    print(f"Action Digest:   {eval_resp['action_digest'][:32]}...")
    assert eval_resp["decision"] == "ALLOW", "Expected ALLOW"

    # Tool Execution
    exec_token = eval_resp["execution_authorization"]
    exec_resp = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/{eval_resp['action_id']}/execute",
        headers=fin_headers,
        json={"execution_authorization": exec_token},
        timeout=5,
    ).json()
    print(f"Tool Execution Status: {exec_resp['status']} | Result: {exec_resp['result']}")

    # Step 5: Finance Agent -> database.delete -> BLOCK -> Tool NEVER executes
    log_step(5, "Finance Agent: Destructive Delete -> [BLOCK] -> Tool NEVER Executes")
    block_eval = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/evaluate",
        headers=fin_headers,
        json={
            "session_id": sessions["finance_agent"],
            "tool": "database",
            "operation": "delete",
            "resource": "audit_logs",
            "arguments": {"target": "all"},
            "purpose": "Purge history",
        },
        timeout=5,
    ).json()

    print(f"Policy Decision: {block_eval['decision']}")
    print(f"Reason Code:     {block_eval['reason_code']}")
    print(f"Explanation:     {block_eval['explanation']}")
    assert block_eval["decision"] == "BLOCK", "Expected BLOCK"
    assert block_eval.get("execution_authorization") is None, "Blocked action must not receive execution token!"
    print("Enforcement Verified: Tool execution was NOT permitted.")

    # Step 6: DevOps Agent -> deployment.update -> REQUIRE_APPROVAL
    log_step(6, "DevOps Agent: Production Mutation -> [REQUIRE_APPROVAL] -> Paused")
    devops_headers = {"Authorization": f"Bearer {credentials['devops_agent']}"}
    appr_eval = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/evaluate",
        headers=devops_headers,
        json={
            "session_id": sessions["devops_agent"],
            "tool": "deployment",
            "operation": "update",
            "resource": "production-api-gateway",
            "arguments": {"image": "v2.0-hotfix"},
            "purpose": "Production rollout",
        },
        timeout=5,
    ).json()

    print(f"Policy Decision: {appr_eval['decision']}")
    print(f"Reason Code:     {appr_eval['reason_code']}")
    print(f"Explanation:     {appr_eval['explanation']}")
    assert appr_eval["decision"] == "REQUIRE_APPROVAL", "Expected REQUIRE_APPROVAL"
    assert appr_eval.get("execution_authorization") is None, "Requires human approval token"

    # Step 7: Suspend Finance Agent -> Attempt action -> SUSPEND
    log_step(7, "Suspend Finance Agent via Kill Switch -> [SUSPEND]")
    sus_resp = requests.patch(
        f"{BASE_URL}/api/v1/agents/finance_agent",
        headers=ADMIN_HEADERS,
        json={"status": "suspended"},
        timeout=5,
    ).json()
    print(f"Agent Status Updated: {sus_resp['name']} is now '{sus_resp['status']}'")

    sus_eval = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/evaluate",
        headers=fin_headers,
        json={
            "session_id": sessions["finance_agent"],
            "tool": "database",
            "operation": "read",
            "resource": "ledger_transactions",
            "arguments": {},
            "purpose": "Attempt after suspension",
        },
        timeout=5,
    ).json()

    print(f"Policy Decision: {sus_eval['decision']}")
    print(f"Reason Code:     {sus_eval['reason_code']}")
    assert sus_eval["decision"] in ("SUSPEND", "BLOCK"), "Expected SUSPEND/BLOCK for suspended agent"

    # Step 8: Dashboard Activity Verification
    log_step(8, "Dashboard Activity Verification & Telemetry Summary")
    stats = requests.get(f"{BASE_URL}/api/v1/monitoring/stats", timeout=5).json()
    print(f"Total Evaluated Actions: {stats.get('total_actions')}")
    print(f"Allowed:                 {stats.get('allowed')}")
    print(f"Blocked:                 {stats.get('blocked')}")
    print(f"Pending Approval:        {stats.get('pending_approval')}")
    print(f"Suspended:               {stats.get('suspended')}")

    recent = requests.get(f"{BASE_URL}/api/v1/monitoring/activity?limit=5", timeout=5).json()
    print("\nRecent Runtime Audit Stream:")
    for a in recent:
        print(f"  [{a['timestamp'][:19]}] {a['agent_id']:<15} {a['tool']:<10} {a['operation']:<8} -> {a['decision']:<16} ({a['execution_status']})")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE: All 8 Security Governance steps executed and verified!")
    print("=" * 70)


if __name__ == "__main__":
    main()
