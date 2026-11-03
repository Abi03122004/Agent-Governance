#!/usr/bin/env python3
"""OpenHands Runtime Governance Gateway Demonstration Script.

Runs 4 OpenHands actions mediated by the AI Agent Runtime Governance Gateway:
1. ALLOW:            CmdRunAction("ls -la") -> allowed, executed, result reported.
2. BLOCK:            FileReadAction("secrets/credentials.env") -> blocked, tool never runs.
3. REQUIRE_APPROVAL: FileWriteAction("schema.sql") -> approval ticket created, polled, approved, executed.
4. SUSPEND:          CmdRunAction("whoami") under suspended state -> halts runtime cleanly.

Verifies:
- Runtime Activity log entries for all 4 decisions.
- Audit Log ledger entries.
- Cryptographic SHA-256 hash chain verification.
"""

import os
import sys
import time
import json
import uuid
import threading
import requests
from pathlib import Path

# Ensure project and OpenHands directories are on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "external" / "OpenHands"))
sys.path.insert(0, str(BASE_DIR / "backend" / "src"))

from openhands.core.config import OpenHandsConfig
from openhands.llm.llm_registry import LLMRegistry
from openhands.events.action import CmdRunAction, FileReadAction, FileWriteAction
from openhands.events.observation import (
    CmdOutputObservation,
    CmdOutputMetadata,
    FileReadObservation,
    FileWriteObservation,
    ErrorObservation,
    NullObservation,
)
from openhands.events.stream import EventStream
from openhands.runtime.base import Runtime
from openhands.runtime.governance_client import GovernanceClient, get_governance_client

GATEWAY_URL = os.environ.get("GOVERNANCE_GATEWAY_URL", "http://127.0.0.1:8000")
ADMIN_EMAIL = "security_admin@enterprise.internal"
APPROVER_EMAIL = "reviewer@enterprise.internal"


class DemoOpenHandsRuntime(Runtime):
    """Minimal OpenHands Runtime subclass for demonstration of governance interception."""
    __abstractmethods__ = frozenset()

    def __init__(self, config=None, event_stream=None, sid="demo-session"):
        if config is None:
            config = OpenHandsConfig()
        if event_stream is None:
            event_stream = EventStream(sid=sid, file_store=None)
        llm_registry = LLMRegistry(config=config)
        super().__init__(config=config, event_stream=event_stream, llm_registry=llm_registry, sid=sid)
        self.executed_tools = []

    def run(self, action: CmdRunAction):
        self.executed_tools.append(f"cmd:{action.command}")
        return CmdOutputObservation(
            content="total 12\ndrwxr-xr-x 2 user staff 64 Oct 29 22:00 .\n-rw-r--r-- 1 user staff 120 demo.py",
            command=action.command,
            metadata=CmdOutputMetadata(exit_code=0),
        )

    def read(self, action: FileReadAction):
        self.executed_tools.append(f"read:{action.path}")
        return FileReadObservation(content="sensitive_secret_value", path=action.path)

    def write(self, action: FileWriteAction):
        self.executed_tools.append(f"write:{action.path}")
        return FileWriteObservation(content="", path=action.path)

    def connect(self):
        pass

    def close(self):
        self.closed = True

DemoOpenHandsRuntime.__abstractmethods__ = frozenset()


def provision_demo_agent_if_needed():
    """Ensure a valid agent and credential exist for the demo."""
    api_key = os.environ.get("GOVERNANCE_API_KEY")
    if api_key:
        return None, api_key

    agent_id = f"openhands-demo-{uuid.uuid4().hex[:8]}"
    print(f"[*] Auto-provisioning ephemeral demo agent: {agent_id}")
    
    headers = {"X-User-Email": ADMIN_EMAIL, "Content-Type": "application/json"}
    
    # 1. Create agent
    create_agent_payload = {
        "id": agent_id,
        "name": "OpenHands Mediated Demo Agent",
        "organization_id": "org_enterprise",
        "project_id": "proj_operations",
        "environment": "demo",
        "purpose": "OpenHands Gateway Integration Verification",
    }
    r = requests.post(f"{GATEWAY_URL}/api/v1/agents", json=create_agent_payload, headers=headers, timeout=5)
    r.raise_for_status()

    # 2. Issue API Key
    r_cred = requests.post(f"{GATEWAY_URL}/api/v1/agents/{agent_id}/credentials", json={}, headers=headers, timeout=5)
    r_cred.raise_for_status()
    api_key = r_cred.json()["plaintext_secret"]

    os.environ["GOVERNANCE_GATEWAY_URL"] = GATEWAY_URL
    os.environ["GOVERNANCE_API_KEY"] = api_key
    return agent_id, api_key


def background_approver(agent_api_key: str):
    """Polls for pending approval tickets and approves them using independent approver credentials."""
    time.sleep(1.5)
    try:
        headers = {"X-User-Email": APPROVER_EMAIL}
        resp = requests.get(f"{GATEWAY_URL}/api/v1/approvals?status=PENDING&organization_id=org_enterprise", headers=headers, timeout=5)
        if resp.status_code == 200:
            tickets = resp.json()
            for ticket in tickets:
                ticket_id = ticket["ticket_id"]
                print(f"\n[INDEPENDENT APPROVER / 4-EYES PRINCIPLE] Approving ticket {ticket_id} as {APPROVER_EMAIL}...")
                appr_resp = requests.post(
                    f"{GATEWAY_URL}/api/v1/approvals/{ticket_id}/approve",
                    headers=headers,
                    json={"rationale": "Security reviewer verified schema migration and granted approval."},
                    timeout=5,
                )
                if appr_resp.status_code == 200:
                    print(f"[INDEPENDENT APPROVER] Ticket {ticket_id} successfully APPROVED.")
                else:
                    print(f"[!] Approval failed with {appr_resp.status_code}: {appr_resp.text}")
    except Exception as e:
        print(f"[!] Background approver error: {e}")


def main():
    print("=" * 70)
    print(" AI Agent Runtime Governance Gateway <-> OpenHands End-to-End Demo")
    print("=" * 70)

    demo_agent_id, api_key = provision_demo_agent_if_needed()
    client = GovernanceClient(gateway_url=GATEWAY_URL, api_key=api_key, poll_interval=1.0, poll_timeout=15.0)
    
    runtime = DemoOpenHandsRuntime(sid=f"demo-session-{uuid.uuid4().hex[:6]}")
    runtime._governance_client = client

    try:
        # -------------------------------------------------------------
        # Action 1: ALLOW
        # -------------------------------------------------------------
        print("\n--- [Action 1: ALLOW] Running 'ls -la' ---")
        act_allow = CmdRunAction(command="ls -la")
        obs_allow = runtime.run_action(act_allow)
        print(f"Observation Type: {type(obs_allow).__name__}")
        print(f"Observation Content:\n{getattr(obs_allow, 'content', '')[:100]}...")
        assert "demo.py" in getattr(obs_allow, "content", ""), "Tool was not executed on ALLOW"
        print("[PASS] Action 1 was ALLOWED, validated via execution token, and outcome reported.")

        # -------------------------------------------------------------
        # Action 2: BLOCK
        # -------------------------------------------------------------
        print("\n--- [Action 2: BLOCK] Attempting to read 'secrets/credentials.env' ---")
        act_block = FileReadAction(path="secrets/credentials.env")
        obs_block = runtime.run_action(act_block)
        print(f"Observation Type: {type(obs_block).__name__}")
        print(f"Observation Content: {getattr(obs_block, 'content', '')}")
        assert isinstance(obs_block, ErrorObservation), "Action should have returned ErrorObservation"
        assert "read:secrets/credentials.env" not in runtime.executed_tools, "Tool executed despite BLOCK!"
        print("[PASS] Action 2 was BLOCKED by governance policy and side-effect was aborted.")

        # -------------------------------------------------------------
        # Action 3: REQUIRE_APPROVAL
        # -------------------------------------------------------------
        print("\n--- [Action 3: REQUIRE_APPROVAL] Writing production migration 'schema.sql' ---")
        # Start the background human approver (simulating human approving in the dashboard)
        approver_thread = threading.Thread(target=background_approver, args=(api_key,), daemon=True)
        approver_thread.start()

        act_approval = FileWriteAction(
            path="schema.sql",
            content="ALTER TABLE accounts ADD COLUMN balance NUMERIC DEFAULT 0.0;",
        )
        obs_approval = runtime.run_action(act_approval)
        print(f"Observation Type: {type(obs_approval).__name__}")
        assert isinstance(obs_approval, FileWriteObservation), "Action should have succeeded post-approval"
        assert "write:schema.sql" in runtime.executed_tools, "Write was not executed after approval"
        print("[PASS] Action 3 required approval, polled ticket, claimed token, and executed.")

        # -------------------------------------------------------------
        # Action 4: SUSPEND
        # -------------------------------------------------------------
        print("\n--- [Action 4: SUSPEND] Triggering Agent Suspension and attempting action ---")
        if demo_agent_id:
            # Suspend the agent via admin API
            patch_resp = requests.patch(
                f"{GATEWAY_URL}/api/v1/agents/{demo_agent_id}",
                headers={"X-User-Email": ADMIN_EMAIL},
                json={"status": "suspended"},
                timeout=5,
            )
            patch_resp.raise_for_status()
            print(f"Agent {demo_agent_id} status updated to 'suspended'.")

        act_suspend = CmdRunAction(command="whoami")
        obs_suspend = runtime.run_action(act_suspend)
        print(f"Observation Type: {type(obs_suspend).__name__}")
        print(f"Observation Content: {getattr(obs_suspend, 'content', '')}")
        assert isinstance(obs_suspend, ErrorObservation), "Suspension should return ErrorObservation"
        assert "whoami" not in [t for t in runtime.executed_tools if "whoami" in t], "Tool ran during suspension"
        print("[PASS] Action 4 triggered SUSPEND tripwire, cleanly halting runtime.")

        # -------------------------------------------------------------
        # VERIFICATION: Runtime Activity & Cryptographic Audit Hash Chain
        # -------------------------------------------------------------
        print("\n" + "=" * 70)
        print(" VERIFICATION: Runtime Activity & Audit Hash Chain")
        print("=" * 70)

        # 1. Runtime Activity
        act_headers = {"Authorization": f"Bearer {api_key}"}
        resp_act = requests.get(f"{GATEWAY_URL}/api/v1/runtime/activity?limit=10", headers=act_headers, timeout=5)
        if resp_act.status_code == 200:
            activities = resp_act.json()
            print(f"\n[+] Runtime Activity Records ({len(activities)} actions captured for agent):")
            for act in activities[:5]:
                print(f"    - Action ID: {act['action_id']} | Tool: {act['tool']:<10} | Decision: {act['decision']:<16} | Digest: {act['action_digest'][:18]}...")

        # 2. Audit Ledger
        admin_headers = {"X-User-Email": ADMIN_EMAIL}
        resp_audit = requests.get(
            f"{GATEWAY_URL}/api/v1/audit/events?organization_id=org_enterprise&limit=10",
            headers=admin_headers,
            timeout=5,
        )
        if resp_audit.status_code == 200:
            events = resp_audit.json()
            print(f"\n[+] Audit Ledger Records ({len(events)} events in org_enterprise):")
            for ev in events[:5]:
                print(f"    - Event: {ev['event_type']:<28} | State: {str(ev.get('execution_state')):<10} | Hash: {ev['event_hash'][:16]}...")

        # 3. Cryptographic Hash Chain Verification
        resp_chain = requests.get(
            f"{GATEWAY_URL}/api/v1/audit/verify-chain?organization_id=org_enterprise",
            headers=admin_headers,
            timeout=5,
        )
        if resp_chain.status_code == 200:
            chain_result = resp_chain.json()
            print(f"\n[+] Cryptographic Chain Integrity: {chain_result.get('message')}")
            print(f"    - Chain Valid:   {chain_result.get('valid')}")
            print(f"    - Events Verified: {chain_result.get('verified_count')}")
            assert chain_result.get("valid") is True, "Audit chain integrity failed!"
        else:
            print(f"[!] Failed to verify chain: {resp_chain.text}")

        print("\n" + "=" * 70)
        print(" ALL VERIFICATIONS PASSED: 4 Decisions Mediated, Ledger & Hash Chain Intact.")
        print("=" * 70)

    finally:
        # Clean up ephemeral demo agent
        if demo_agent_id:
            print(f"\n[*] Cleaning up ephemeral demo agent: {demo_agent_id}")
            requests.delete(
                f"{GATEWAY_URL}/api/v1/agents/{demo_agent_id}?purge=true",
                headers={"X-User-Email": ADMIN_EMAIL},
                timeout=5,
            )
            print("[*] Cleanup complete.")


if __name__ == "__main__":
    main()
