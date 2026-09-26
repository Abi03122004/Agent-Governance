"""Support Agent: Demonstrate permitted customer case lookups with dedicated agent identity."""

import os
import requests
from client_helper import get_or_create_agent_credential

BASE_URL = os.getenv("GOVERNANCE_URL", "http://localhost:8000")
TOKEN = get_or_create_agent_credential("support_agent", "Support Agent", "Customer ticket analysis and resolution")

headers = {"Authorization": f"Bearer {TOKEN}"}

# 1. Establish runtime session
session = requests.post(f"{BASE_URL}/api/v1/runtime/sessions", headers=headers, timeout=10).json()
session_id = session["session_id"]
print(f"[Support Agent] Established isolated session: {session_id}")

# 2. Evaluate permitted read on support_cases
print("\n[Support Agent] Requesting read on support_cases...")
response = requests.post(
    f"{BASE_URL}/api/v1/runtime/actions/evaluate",
    headers=headers,
    timeout=10,
    json={
        "session_id": session_id,
        "tool": "safe_echo",
        "operation": "read",
        "resource": "support_cases",
        "arguments": {"case_id": "case-9941"},
        "purpose": "Retrieve ticket details for user query",
    },
).json()

print(f" -> Decision:    {response.get('decision')}")
print(f" -> Reason Code: {response.get('reason_code')}")
print(f" -> Action Digest: {response.get('action_digest', '')[:24]}...")

if response.get("decision") == "ALLOW":
    exec_res = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/{response['action_id']}/execute",
        headers=headers,
        json={"execution_authorization": response["execution_authorization"]},
        timeout=10,
    ).json()
    print(f" -> Safe Tool Executed: {exec_res.get('result')}")
