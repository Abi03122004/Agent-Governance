"""DevOps Agent: Demonstrate production mutation intercept resulting in REQUIRE_APPROVAL."""

import os
import requests
from client_helper import get_or_create_agent_credential

BASE_URL = os.getenv("GOVERNANCE_URL", "http://localhost:8000")
TOKEN = get_or_create_agent_credential("devops_agent", "DevOps Agent", "Cluster management and continuous delivery")

headers = {"Authorization": f"Bearer {TOKEN}"}

# 1. Establish runtime session
session = requests.post(f"{BASE_URL}/api/v1/runtime/sessions", headers=headers, timeout=10).json()
session_id = session["session_id"]
print(f"[DevOps Agent] Established isolated session: {session_id}")

# 2. Evaluate high-impact production update
print("\n[DevOps Agent] Requesting deployment.update on production cluster...")
response = requests.post(
    f"{BASE_URL}/api/v1/runtime/actions/evaluate",
    headers=headers,
    timeout=10,
    json={
        "session_id": session_id,
        "tool": "deployment",
        "operation": "update",
        "resource": "production-api-gateway",
        "arguments": {"version": "v2.4.1", "traffic_shift": "25%"},
        "purpose": "Canary rollout of updated service",
    },
).json()

print(f" -> Decision:    {response.get('decision')}")
print(f" -> Reason Code: {response.get('reason_code')}")
print(f" -> Explanation: {response.get('explanation')}")
print(f" -> Action Digest: {response.get('action_digest', '')[:24]}...")

if response.get("decision") == "REQUIRE_APPROVAL":
    print(" -> Verification: Automatic execution frozen. Awaiting human approver cryptographic signature.")
