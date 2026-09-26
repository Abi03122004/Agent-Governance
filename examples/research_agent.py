"""Research Agent: Demonstrate safe document read (ALLOW) and unauthorized secrets access (BLOCK)."""

import os
import requests
from client_helper import get_or_create_agent_credential

BASE_URL = os.getenv("GOVERNANCE_URL", "http://localhost:8000")
TOKEN = get_or_create_agent_credential("research_agent", "Research Agent", "Market intelligence and literature review")

headers = {"Authorization": f"Bearer {TOKEN}"}

# 1. Create a runtime session
session_resp = requests.post(f"{BASE_URL}/api/v1/runtime/sessions", headers=headers, timeout=10)
session_resp.raise_for_status()
session = session_resp.json()
session_id = session["session_id"]
print(f"[Research Agent] Active Session: {session_id}")

# 2. Permitted research document lookup
print("\n[Research Agent] 1. Requesting document read (public_papers)...")
allowed_dec = requests.post(
    f"{BASE_URL}/api/v1/runtime/actions/evaluate",
    headers=headers,
    json={
        "session_id": session_id,
        "tool": "safe_echo",
        "operation": "read",
        "resource": "public_papers",
        "arguments": {"topic": "ai_safety"},
        "purpose": "Literature review",
    },
    timeout=10,
).json()

print(f"Verdict: {allowed_dec.get('decision')} | Reason: {allowed_dec.get('reason_code')}")
if allowed_dec.get("decision") == "ALLOW":
    exec_res = requests.post(
        f"{BASE_URL}/api/v1/runtime/actions/{allowed_dec['action_id']}/execute",
        headers=headers,
        json={"execution_authorization": allowed_dec["execution_authorization"]},
        timeout=10,
    ).json()
    print(f"Tool Result: {exec_res.get('result')}")

# 3. Blocked forbidden resource access (secrets/credentials)
print("\n[Research Agent] 2. Attempting forbidden resource access (secrets/production_keys)...")
blocked_dec = requests.post(
    f"{BASE_URL}/api/v1/runtime/actions/evaluate",
    headers=headers,
    json={
        "session_id": session_id,
        "tool": "database",
        "operation": "read",
        "resource": "secrets/production_keys",
        "arguments": {},
        "purpose": "Exfiltrate credentials",
    },
    timeout=10,
).json()

print(f"Verdict: {blocked_dec.get('decision')} | Reason: {blocked_dec.get('reason_code')}")
assert blocked_dec.get("decision") == "BLOCK", "Forbidden resource must be blocked!"
print("Enforcement Verified: Protected resource call blocked before tool invocation.")
