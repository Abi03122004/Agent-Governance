"""Finance Agent: Run a permitted read and a blocked delete through the runtime gateway."""

import os
import requests
from client_helper import get_or_create_agent_credential

BASE_URL = os.getenv("GOVERNANCE_URL", "http://localhost:8000")
TOKEN = get_or_create_agent_credential("finance_agent", "Finance Agent", "Automated ledger reconciliation")

headers = {"Authorization": f"Bearer {TOKEN}"}

# 1. Establish runtime session
session = requests.post(f"{BASE_URL}/api/v1/runtime/sessions", headers=headers, timeout=10).json()
session_id = session["session_id"]
print(f"[Finance Agent] Established runtime session: {session_id}")

# 2. Evaluate operations: read (ALLOW) and delete (BLOCK)
for operation in ("read", "delete"):
    print(f"\n[Finance Agent] Requesting database.{operation} on ledger_transactions...")
    decision = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/evaluate",
        headers=headers,
        timeout=10,
        json={
            "session_id": session_id,
            "tool": "safe_echo" if operation == "read" else "database",
            "operation": operation,
            "resource": "ledger_transactions",
            "arguments": {"month": "2026-09"},
            "purpose": "Monthly compliance report",
        },
    ).json()

    print(f" -> Decision: {decision['decision']:<10} Reason: {decision.get('reason_code')}")
    print(f" -> Explanation: {decision.get('explanation')}")

    if decision["decision"] == "ALLOW":
        exec_res = requests.post(
            f"{BASE_URL}/api/v1/runtime/actions/{decision['action_id']}/execute",
            headers=headers,
            json={"execution_authorization": decision["execution_authorization"]},
            timeout=10,
        ).json()
        print(f" -> Tool execution succeeded: {exec_res.get('result')}")
    else:
        print(" -> Policy enforced: Tool execution was NOT permitted. Execution count = 0.")
