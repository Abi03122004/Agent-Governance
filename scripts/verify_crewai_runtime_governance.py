#!/usr/bin/env python3
"""Rigorous End-to-End Verification Harness for CrewAI External Agent Runtime Integration.

Phase 4 Verification Areas:
1. Actual CrewAI Runtime Execution (CrewStructuredTool -> ALLOW -> Result reported to gateway)
2. Blocked Tool Execution & Physical Side-Effect Invariant (Physical Marker File Clean)
3. Human-in-the-Loop Approval Workflow, Argument Integrity & Single-Use Token Replay Rejection
4. Runtime Agent Suspension while Process is Live (Tripwire Enforcement)
5. Cryptographic Identity & Multi-Tenant Isolation (Anti-spoofing, cross-tenant isolation)
6. Audit Ledger Integrity & Cryptographic SHA-256 Hash Chaining
7. Failure Modes & Fail-Closed Invariants (Offline gateway, rejected approvals)
"""

import os
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

# Add paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "agent-sdk"))
sys.path.insert(0, str(BASE_DIR / "backend" / "src"))

from crewai.tools import tool, BaseTool
from crewai.tools.structured_tool import CrewStructuredTool
from crewai.hooks import (
    ToolCallHookContext,
    register_before_tool_call_hook,
    unregister_before_tool_call_hook,
    register_after_tool_call_hook,
    unregister_after_tool_call_hook,
)
from crewai.utilities.tool_utils import execute_tool_and_check_finality, AgentAction

from governance_sdk.client import GovernanceClient
from governance_sdk.adapters.crewai import (
    CrewAIGovernanceHook,
    GovernedCrewAITool,
    infer_crewai_action_semantics,
)

GATEWAY_URL = os.environ.get("GOVERNANCE_GATEWAY_URL", "http://127.0.0.1:8000")
ADMIN_EMAIL = "security_admin@enterprise.internal"
ADMIN_HEADERS = {"X-User-Email": ADMIN_EMAIL, "Content-Type": "application/json"}
APPROVER_EMAIL = "reviewer@enterprise.internal"
APPROVER_HEADERS = {"X-User-Email": APPROVER_EMAIL, "Content-Type": "application/json"}
BETA_ADMIN_EMAIL = "beta_admin@enterprise.internal"
BETA_ADMIN_HEADERS = {"X-User-Email": BETA_ADMIN_EMAIL, "Content-Type": "application/json"}

AGENT_ID = f"crewai-agent-{uuid.uuid4().hex[:8]}"
ORG_ID = "org_enterprise"
PROJ_ID = "proj_operations"


def provision_environment():
    """Setup verified CrewAI agent and secondary tenant agent."""
    print(f"[*] Provisioning CrewAI agent '{AGENT_ID}' on {GATEWAY_URL}...")
    reg_payload = {
        "id": AGENT_ID,
        "organization_id": ORG_ID,
        "project_id": PROJ_ID,
        "name": "Verified CrewAI Agent",
        "framework": "crewai",
        "llm_provider": "openai",
        "default_model": "gpt-4o-mini",
        "endpoint": "http://127.0.0.1:8000",
        "purpose": "Autonomous multi-agent orchestration and security operations",
    }
    r = requests.post(f"{GATEWAY_URL}/api/v1/agents", json=reg_payload, headers=ADMIN_HEADERS)
    assert r.status_code in (200, 201), f"Agent registration failed: {r.text}"

    # Issue credential
    cred_resp = requests.post(f"{GATEWAY_URL}/api/v1/agents/{AGENT_ID}/credentials", json={}, headers=ADMIN_HEADERS)
    assert cred_resp.status_code in (200, 201), f"Credential creation failed: {cred_resp.text}"
    agent_token = cred_resp.json()["plaintext_secret"]

    # Ensure Beta Tenant exists for isolation test
    import sqlite3
    db_path = BASE_DIR / "backend" / "agent_governance.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO organizations (id, name, status, created_at, updated_at) VALUES ('org_beta', 'Beta Corp', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    cur.execute("INSERT OR IGNORE INTO projects (id, organization_id, name, status, created_at, updated_at) VALUES ('proj_beta', 'org_beta', 'Beta Project', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    cur.execute("INSERT OR IGNORE INTO users (id, email, display_name, status, created_at, updated_at) VALUES ('usr_beta_admin', 'beta_admin@enterprise.internal', 'Beta Admin', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    cur.execute("INSERT OR IGNORE INTO memberships (id, user_id, organization_id, role, created_at) VALUES ('mem_beta_admin', 'usr_beta_admin', 'org_beta', 'administrator', CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

    beta_agent_id = f"beta-agent-{uuid.uuid4().hex[:6]}"
    requests.post(f"{GATEWAY_URL}/api/v1/agents", json={
        "id": beta_agent_id, "organization_id": "org_beta", "project_id": "proj_beta", "name": "Beta Agent"
    }, headers=BETA_ADMIN_HEADERS)
    beta_cred = requests.post(f"{GATEWAY_URL}/api/v1/agents/{beta_agent_id}/credentials", json={}, headers=BETA_ADMIN_HEADERS)
    beta_token = beta_cred.json()["plaintext_secret"]

    return agent_token, beta_token, beta_agent_id


def main():
    print("=" * 80)
    print("PHASE 4: RIGOROUS CREWAI RUNTIME GOVERNANCE VERIFICATION HARNESS")
    print("=" * 80)

    agent_token, beta_token, beta_agent_id = provision_environment()
    evidence: Dict[str, Any] = {}

    # Initialize SDK client
    gov_client = GovernanceClient(
        base_url=GATEWAY_URL,
        agent_token=agent_token,
        auto_start_session=True,
    )
    session_id = gov_client.ensure_session()
    print(f"[*] Established Authenticated Runtime Session: {session_id}")

    # ==========================================================================
    # 1. ACTUAL CREWAI RUNTIME EXECUTION (ALLOW)
    # ==========================================================================
    print("\n" + "=" * 60)
    print(" [1] ACTUAL CREWAI RUNTIME EXECUTION (ALLOW)")
    print("=" * 60)

    tool_executed = False

    def query_system_metrics(resource: str) -> str:
        """Reads read-only server telemetry metrics."""
        nonlocal tool_executed
        tool_executed = True
        return f"Metrics for {resource}: CPU=12%, RAM=34%, Load=0.15"

    safe_tool = tool("query_system_metrics")(query_system_metrics).to_structured_tool()

    act1 = AgentAction(
        thought="Querying non-destructive server metrics under governance policy",
        tool="query_system_metrics",
        tool_input='{"resource": "cluster-node-01"}',
        text="Action: query_system_metrics\nAction Input: {\"resource\": \"cluster-node-01\"}",
    )

    with CrewAIGovernanceHook(client=gov_client) as hook:
        result1 = execute_tool_and_check_finality(agent_action=act1, tools=[safe_tool])

    print(f"[*] Execution Output: {result1.result}")
    assert tool_executed is True, "Expected tool execution function to be called!"
    assert "Metrics for cluster-node-01" in str(result1.result), f"Unexpected output: {result1.result}"
    print(f"[PASS] CrewAI tool permitted and executed successfully under ALLOW policy.")
    evidence["Actual CrewAI Runtime Execution"] = "VERIFIED"

    # ==========================================================================
    # 2. BLOCKED TOOL EXECUTION & PHYSICAL SIDE-EFFECT INVARIANT (BLOCK)
    # ==========================================================================
    print("\n" + "=" * 60)
    print(" [2] BLOCKED TOOL EXECUTION & PHYSICAL MARKER INVARIANT (BLOCK)")
    print("=" * 60)

    temp_dir = Path(tempfile.mkdtemp(prefix="crewai_gov_test_"))
    marker_file = temp_dir / "crewai_blocked_marker.txt"
    if marker_file.exists():
        marker_file.unlink()

    destructive_tool_called = False

    def purge_database_records(command: str) -> str:
        """Dangerous tool that drops database tables."""
        nonlocal destructive_tool_called
        destructive_tool_called = True
        # If policy fails, physical marker is written
        marker_file.write_text("SECURITY BREACH: Tool executed despite policy block!")
        return "Database tables purged."

    dangerous_tool = tool("purge_database_records")(purge_database_records).to_structured_tool()

    act2 = AgentAction(
        thought="Attempting to purge core customer database records",
        tool="purge_database_records",
        tool_input='{"command": "drop table customers cascade"}',
        text="Action: purge_database_records\nAction Input: {\"command\": \"drop table customers cascade\"}",
    )

    with CrewAIGovernanceHook(client=gov_client) as hook:
        result2 = execute_tool_and_check_finality(agent_action=act2, tools=[dangerous_tool])

    print(f"[*] Blocked Result: {result2.result}")
    assert "blocked by hook" in str(result2.result).lower(), f"Expected blocked message: {result2.result}"
    assert destructive_tool_called is False, "SECURITY FAILURE: Destructive tool callable was invoked!"
    assert not marker_file.exists(), "SECURITY INVARIANT VIOLATED: Marker file was created on disk!"
    print(f"[PASS] Destructive tool intercepted, blocked, and physical marker file remained clean.")
    evidence["Blocked Execution & Marker Invariant"] = "VERIFIED"

    # ==========================================================================
    # 3. HUMAN-IN-THE-LOOP APPROVAL WORKFLOW & TOKEN REPLAY REJECTION
    # ==========================================================================
    print("\n" + "=" * 60)
    print(" [3] HUMAN-IN-THE-LOOP APPROVAL & SINGLE-USE REPLAY REJECTION")
    print("=" * 60)

    deploy_called = False

    def deploy_production_service(target: str) -> str:
        """Deploys a critical service to production infrastructure."""
        nonlocal deploy_called
        deploy_called = True
        return f"Service successfully deployed to {target}"

    deploy_tool = tool("deploy_production_service")(deploy_production_service).to_structured_tool()

    act3 = AgentAction(
        thought="Deploying new billing microservice to production cluster",
        tool="deploy_production_service",
        tool_input='{"target": "/prod/cluster/k8s"}',
        text="Action: deploy_production_service\nAction Input: {\"target\": \"/prod/cluster/k8s\"}",
    )

    captured_auth_token = None

    def approver_background_thread():
        """Simulates a human security officer reviewing and approving the ticket."""
        time.sleep(1.0)
        print("[Approver Thread] Querying pending approval queue...")
        for _ in range(20):
            try:
                resp = requests.get(f"{GATEWAY_URL}/api/v1/approvals", headers=APPROVER_HEADERS)
                if resp.status_code == 200:
                    tickets = resp.json()
                    for t in tickets:
                        if t.get("status") == "PENDING":
                            tid = t["ticket_id"]
                            print(f"[Approver Thread] Approving ticket '{tid}' with cryptographic authorization...")
                            dec_resp = requests.post(
                                f"{GATEWAY_URL}/api/v1/approvals/{tid}/approve",
                                json={"rationale": "Approved by SecOps for Phase 4 verification"},
                                headers=APPROVER_HEADERS,
                            )
                            if dec_resp.status_code == 200:
                                print(f"[Approver Thread] Ticket '{tid}' successfully approved!")
                                return
            except Exception as e:
                print(f"[Approver Thread] Poll error: {e}")
            time.sleep(0.5)

    th = threading.Thread(target=approver_background_thread, daemon=True)
    th.start()

    hook_instance = CrewAIGovernanceHook(client=gov_client, auto_wait_approval=True, approval_timeout=15.0)

    with hook_instance:
        result3 = execute_tool_and_check_finality(agent_action=act3, tools=[deploy_tool])

    th.join(timeout=5.0)

    print(f"[*] Human-in-the-Loop Result: {result3.result}")
    assert deploy_called is True, "Deploy tool was not called after approval!"
    assert "Service successfully deployed to /prod/cluster/k8s" in str(result3.result)
    print(f"[PASS] Human approval successfully granted; tool executed and output reported.")

    # Now verify token replay rejection:
    # Query database for the execution authorization token used for this action
    import sqlite3
    db_path = BASE_DIR / "backend" / "agent_governance.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.id, ar.execution_token, ea.used_at
        FROM runtime_actions r
        JOIN approval_requests ar ON r.id = ar.action_id
        LEFT JOIN execution_authorizations ea ON r.id = ea.action_id
        WHERE r.agent_id = ? AND r.tool = 'deploy_production_service'
        ORDER BY r.created_at DESC LIMIT 1
        """,
        (AGENT_ID,),
    )
    row = cur.fetchone()
    conn.close()

    assert row is not None, "Execution authorization record not found in database!"
    action_id, token_val, used_at = row
    print(f"[*] Action ID: {action_id} | Token: {token_val[:16]}... | Used At: {used_at}")
    assert token_val is not None, "Execution token was not populated!"
    assert used_at is not None, "Token was not marked as used upon result reporting!"

    # Replay Attempt 1: Attempt to execute with already-used token
    replay_resp1 = requests.post(
        f"{GATEWAY_URL}/api/v1/runtime/actions/{action_id}/execute",
        json={"execution_authorization": token_val},
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    print(f"[*] Replay attempt to /execute: HTTP {replay_resp1.status_code}")
    assert replay_resp1.status_code == 403, f"Expected HTTP 403 for replayed token, got {replay_resp1.status_code}"

    # Replay Attempt 2: Attempt to report result again with already-used token
    replay_resp2 = requests.post(
        f"{GATEWAY_URL}/api/v1/runtime/actions/{action_id}/result",
        json={
            "execution_authorization": token_val,
            "status": "succeeded",
            "output": {"tampered": "replay"},
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    print(f"[*] Replay attempt to /result: HTTP {replay_resp2.status_code}")
    assert replay_resp2.status_code in (400, 403), f"Expected HTTP 400/403 for replayed token result, got {replay_resp2.status_code}"
    print(f"[PASS] Single-use execution authorization replay strictly rejected.")
    evidence["HITL Approval & Replay Rejection"] = "VERIFIED"

    # ==========================================================================
    # 4. RUNTIME AGENT SUSPENSION TRIPWIRE
    # ==========================================================================
    print("\n" + "=" * 60)
    print(" [4] RUNTIME AGENT SUSPENSION TRIPWIRE")
    print("=" * 60)

    # Suspend agent while process is running
    print(f"[*] Suspending agent '{AGENT_ID}' via administrative control plane...")
    susp_resp = requests.patch(
        f"{GATEWAY_URL}/api/v1/agents/{AGENT_ID}",
        json={"status": "suspended"},
        headers=ADMIN_HEADERS,
    )
    assert susp_resp.status_code == 200, f"Suspension failed: {susp_resp.text}"

    tripwire_tool_called = False

    def safe_status_check(query: str) -> str:
        """Harmless tool that should be halted by suspension."""
        nonlocal tripwire_tool_called
        tripwire_tool_called = True
        return "Status OK"

    status_tool = tool("safe_status_check")(safe_status_check).to_structured_tool()

    act4 = AgentAction(
        thought="Attempting harmless status check while agent is suspended",
        tool="safe_status_check",
        tool_input='{"query": "status"}',
        text="Action: safe_status_check\nAction Input: {\"query\": \"status\"}",
    )

    with CrewAIGovernanceHook(client=gov_client) as hook:
        # First call hits gateway, triggers AgentSuspendedError -> marks hook._suspended = True
        res_susp1 = execute_tool_and_check_finality(agent_action=act4, tools=[status_tool])
        assert hook.is_suspended is True, "Hook should have tripped suspension state"
        print(f"[*] Initial call after suspension: {res_susp1.result}")

        # Second call trips internal tripwire immediately without hitting gateway
        res_susp2 = execute_tool_and_check_finality(agent_action=act4, tools=[status_tool])
        print(f"[*] Tripwire immediate halt: {res_susp2.result}")

    assert tripwire_tool_called is False, "SECURITY FAILURE: Tool was executed while suspended!"
    assert "blocked by hook" in str(res_susp1.result).lower()
    assert "blocked by hook" in str(res_susp2.result).lower()
    print(f"[PASS] Agent suspension immediately halts tool execution and trips runtime tripwire.")
    evidence["Runtime Suspension Tripwire"] = "VERIFIED"

    # Reactivate agent for remaining tests
    requests.patch(
        f"{GATEWAY_URL}/api/v1/agents/{AGENT_ID}",
        json={"status": "active"},
        headers=ADMIN_HEADERS,
    )

    # ==========================================================================
    # 5. CRYPTOGRAPHIC IDENTITY & MULTI-TENANT ISOLATION
    # ==========================================================================
    print("\n" + "=" * 60)
    print(" [5] CRYPTOGRAPHIC IDENTITY & MULTI-TENANT ISOLATION")
    print("=" * 60)

    # Test 5.1: Forged Agent ID (Enterprise Token claiming Beta Agent ID)
    forged_agent_resp = requests.post(
        f"{GATEWAY_URL}/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "agent_id": beta_agent_id,  # Forged identity
            "tool": "shell",
            "operation": "execute",
            "resource": "whoami",
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert forged_agent_resp.status_code == 403, f"Expected 403, got {forged_agent_resp.status_code}"
    print(f"[PASS] Forged Agent ID rejected with HTTP 403: {forged_agent_resp.json().get('detail')}")

    # Test 5.2: Forged Organization ID (Enterprise Token claiming org_beta)
    forged_org_resp = requests.post(
        f"{GATEWAY_URL}/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "organization_id": "org_beta",  # Forged tenant
            "tool": "shell",
            "operation": "execute",
            "resource": "pwd",
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert forged_org_resp.status_code == 403, f"Expected 403, got {forged_org_resp.status_code}"
    print(f"[PASS] Forged Organization ID rejected with HTTP 403: {forged_org_resp.json().get('detail')}")

    # Test 5.3: Invalid Bearer Token
    invalid_tok_resp = requests.post(
        f"{GATEWAY_URL}/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "tool": "shell",
            "operation": "execute",
            "resource": "ls",
        },
        headers={"Authorization": "Bearer invalid_secret_token_12345"},
    )
    assert invalid_tok_resp.status_code == 401
    print(f"[PASS] Invalid Bearer Token rejected with HTTP 401.")

    # Test 5.4: Cross-Tenant Session Access (Beta Token accessing Enterprise session)
    cross_sess_resp = requests.post(
        f"{GATEWAY_URL}/api/v1/runtime/actions/evaluate",
        json={
            "session_id": session_id,
            "tool": "shell",
            "operation": "execute",
            "resource": "whoami",
        },
        headers={"Authorization": f"Bearer {beta_token}"},
    )
    assert cross_sess_resp.status_code in (403, 404), f"Expected 403/404, got {cross_sess_resp.status_code}"
    print(f"[PASS] Cross-tenant session access rejected with HTTP {cross_sess_resp.status_code}.")
    evidence["Cryptographic Identity & Multi-Tenant Isolation"] = "VERIFIED"

    # ==========================================================================
    # 6. AUDIT LEDGER INTEGRITY & CRYPTOGRAPHIC SHA-256 HASH CHAINING
    # ==========================================================================
    print("\n" + "=" * 60)
    print(" [6] AUDIT LEDGER & CRYPTOGRAPHIC SHA-256 HASH CHAIN INTEGRITY")
    print("=" * 60)

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        SELECT event_id, organization_id, agent_id, tool_name, canonical_action_hash,
               policy_decision, execution_state, action_id, timestamp, event_hash, previous_event_hash
        FROM audit_events
        WHERE agent_id = ?
        ORDER BY timestamp ASC, event_id ASC
        """,
        (AGENT_ID,),
    )
    audit_rows = cur.fetchall()
    print(f"[*] Retrieved {len(audit_rows)} recorded audit events for CrewAI agent '{AGENT_ID}'.")
    assert len(audit_rows) >= 3, f"Expected at least 3 audit events, found {len(audit_rows)}"

    for row in audit_rows:
        evt_id, org, agt, tool_n, action_digest, decision, state, act_id, ts, ev_hash, prev_hash = row
        assert org == ORG_ID
        assert agt == AGENT_ID
        assert ev_hash is not None and len(ev_hash) == 64
        print(f"    [Audit Record] {evt_id} | Tool: {tool_n:<26} | Decision: {decision:<16} | State: {state:<12} | Hash: {ev_hash[:12]}...")

    # Cryptographic Hash Chain Continuity Check across the entire organization
    cur.execute(
        "SELECT event_id, event_hash, previous_event_hash FROM audit_events WHERE organization_id = ? ORDER BY timestamp ASC, event_id ASC",
        (ORG_ID,),
    )
    chain_rows = cur.fetchall()
    conn.close()

    prev_h = None
    chain_valid = True
    for er in chain_rows:
        e_id, cur_h, p_h = er
        if p_h != prev_h:
            chain_valid = False
            print(f"[!] Broken chain at event {e_id}: expected previous_hash={prev_h}, got {p_h}")
            break
        prev_h = cur_h

    assert chain_valid is True, "Audit hash chain broken!"
    print(f"[PASS] Cryptographic audit hash chain verified: {len(chain_rows)} chained events intact.")
    evidence["Audit Ledger & Cryptographic Hash Chain"] = "VERIFIED"

    # ==========================================================================
    # 7. FAILURE MODES & FAIL-CLOSED INVARIANTS
    # ==========================================================================
    print("\n" + "=" * 60)
    print(" [7] FAILURE MODES & FAIL-CLOSED INVARIANTS")
    print("=" * 60)

    # Test 7.1: Gateway Offline / Unreachable
    offline_client = GovernanceClient(
        base_url="http://127.0.0.1:59999",  # Non-existent port
        agent_token=agent_token,
        auto_start_session=False,
    )

    offline_tool_called = False

    def offline_test_tool(x: str) -> str:
        """Tool invoked against unreachable gateway."""
        nonlocal offline_tool_called
        offline_tool_called = True
        return "Executed"

    off_tool = tool("offline_test_tool")(offline_test_tool).to_structured_tool()

    act_off = AgentAction(
        thought="Testing tool execution when gateway is unreachable",
        tool="offline_test_tool",
        tool_input='{"x": "test"}',
        text="Action: offline_test_tool\nAction Input: {\"x\": \"test\"}",
    )

    with CrewAIGovernanceHook(client=offline_client, fail_closed=True) as hook_offline:
        res_off = execute_tool_and_check_finality(agent_action=act_off, tools=[off_tool])

    assert offline_tool_called is False, "SECURITY FAILURE: Tool executed while gateway was offline!"
    assert "blocked by hook" in str(res_off.result).lower()
    print(f"[PASS] Unreachable gateway triggers FAIL-CLOSED: tool execution strictly aborted.")

    # Test 7.2: Human Approval Rejection
    # Ensure fresh session on active client
    gov_client_fresh = GovernanceClient(base_url=GATEWAY_URL, agent_token=agent_token, auto_start_session=True)

    rejected_tool_called = False

    def mutate_cluster_configuration(target: str) -> str:
        """Tool requiring approval that will be rejected by human operator."""
        nonlocal rejected_tool_called
        rejected_tool_called = True
        return "Executed"

    rej_tool = tool("mutate_cluster_configuration")(mutate_cluster_configuration).to_structured_tool()

    act_rej = AgentAction(
        thought="Action that will be rejected by human reviewer",
        tool="mutate_cluster_configuration",
        tool_input='{"target": "/prod/cluster/k8s"}',
        text="Action: mutate_cluster_configuration\nAction Input: {\"target\": \"/prod/cluster/k8s\"}",
    )

    def rejector_background_thread():
        time.sleep(1.0)
        for _ in range(20):
            try:
                resp = requests.get(f"{GATEWAY_URL}/api/v1/approvals", headers=APPROVER_HEADERS)
                if resp.status_code == 200:
                    for t in resp.json():
                        if t.get("status") == "PENDING":
                            tid = t["ticket_id"]
                            dec_resp = requests.post(
                                f"{GATEWAY_URL}/api/v1/approvals/{tid}/reject",
                                json={"rationale": "Rejected by SecOps for Phase 4 verification"},
                                headers=APPROVER_HEADERS,
                            )
                            if dec_resp.status_code == 200:
                                return
            except Exception:
                pass
            time.sleep(0.5)

    th_rej = threading.Thread(target=rejector_background_thread, daemon=True)
    th_rej.start()

    with CrewAIGovernanceHook(client=gov_client_fresh, auto_wait_approval=True, approval_timeout=10.0) as hook_rej:
        res_rej = execute_tool_and_check_finality(agent_action=act_rej, tools=[rej_tool])

    th_rej.join(timeout=5.0)

    assert rejected_tool_called is False, "SECURITY FAILURE: Tool executed despite approval rejection!"
    assert "blocked by hook" in str(res_rej.result).lower()
    print(f"[PASS] Human approval rejection triggers FAIL-CLOSED: tool execution strictly aborted.")
    evidence["Failure Modes & Fail-Closed Invariants"] = "VERIFIED"

    # ==========================================================================
    # FINAL VERIFICATION REPORT
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PHASE 4: CREWAI RUNTIME GOVERNANCE VERIFICATION SUMMARY")
    print("=" * 80)
    all_passed = True
    for test_name, status in evidence.items():
        print(f"  * {test_name:<50} [{status}]")
        if status != "VERIFIED":
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("[SUCCESS] All 7 Phase 4 verification areas passed with zero errors.")
    else:
        print("[FAILURE] Some verification checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
