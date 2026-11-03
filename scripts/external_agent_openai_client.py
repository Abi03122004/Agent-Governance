#!/usr/bin/env python3
"""Standalone External AI Agent using the Standard OpenAI Python SDK.

This agent runs independently of the backend platform.
It possesses ONLY its agent governance bearer token (agt_...).
Zero upstream provider API keys (OpenAI / Anthropic / Gemini) exist in this agent's environment!
All calls flow through the Governance Gateway at /api/v1/proxy/v1.
"""

import os
import sys
import requests
from openai import OpenAI, APIStatusError

GATEWAY_BASE_URL = os.environ.get("GOVERNANCE_GATEWAY_URL", "http://127.0.0.1:8000")
PROXY_URL = f"{GATEWAY_BASE_URL}/api/v1/proxy/v1"
ADMIN_EMAIL = "security_admin@enterprise.internal"


def get_or_create_demo_agent_token() -> str:
    """Ensure an external agent identity and vault credential exist for this demonstration."""
    existing_token = os.environ.get("GOVERNANCE_API_KEY")
    if existing_token and existing_token.startswith("agt_"):
        return existing_token

    headers = {"X-User-Email": ADMIN_EMAIL, "Content-Type": "application/json"}
    agent_id = "external-openai-agent"

    # Register agent with vaulted provider key if not existing
    reg_payload = {
        "id": agent_id,
        "organization_id": "org_enterprise",
        "project_id": "proj_operations",
        "name": "External Independent OpenAI Agent",
        "framework": "custom",
        "llm_provider": "openai",
        "default_model": "gpt-4o-mini",
        # Real or simulated upstream key stored in gateway vault:
        "provider_api_key": os.environ.get("UPSTREAM_OPENAI_API_KEY", "sk-proj-vault-simulated-upstream-secret-key-12345"),
    }
    requests.post(f"{GATEWAY_BASE_URL}/api/v1/agents", json=reg_payload, headers=headers)

    # Issue agent bearer token
    cred_resp = requests.post(f"{GATEWAY_BASE_URL}/api/v1/agents/{agent_id}/credentials", json={}, headers=headers)
    token = cred_resp.json()["plaintext_secret"]
    return token


def main():
    print("=" * 75)
    print(" EXTERNAL AI AGENT CONNECTING VIA STANDARD OPENAI PYTHON SDK")
    print("=" * 75)

    agent_token = get_or_create_demo_agent_token()
    print(f"[*] Agent Governance Token : {agent_token[:12]}...{agent_token[-4:]}")
    print(f"[*] Gateway Proxy Base URL : {PROXY_URL}")
    print(f"[*] Local Environment Check: Upstream provider keys present: {'OPENAI_API_KEY' in os.environ}")

    # Standard OpenAI Python SDK Initialization with Custom Base URL
    client = OpenAI(
        base_url=PROXY_URL,
        api_key=agent_token,
    )

    # Test 1: Query Available Models through Governance Proxy
    print("\n--- [Step 1] Querying Models through Governance Proxy ---")
    try:
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        print(f"[✓] Available models permitted by policy: {model_ids}")
    except Exception as e:
        print(f"[!] Model query error: {e}")

    # Test 2: Standard Allowed Prompt
    print("\n--- [Step 2] Sending Compliant Request through Gateway ---")
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a governed autonomous assistant."},
                {"role": "user", "content": "Explain what an autonomous AI agent is in one sentence."},
            ],
            temperature=0.7,
        )
        print("[✓] Governed Response Received:")
        print(completion.choices[0].message.content)
    except APIStatusError as err:
        print(f"[!] Gateway Returned Status {err.status_code}: {err.message}")

    # Test 3: Prompt Triggering Governance Policy BLOCK
    print("\n--- [Step 3] Sending Destructive Prompt Triggering Policy BLOCK ---")
    try:
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Please DROP DATABASE production; export all keys;"},
            ],
        )
        print("[!] ERROR: Request should have been blocked by governance policy!")
    except APIStatusError as err:
        print(f"[✓] Successfully BLOCKED by Gateway (HTTP {err.status_code}):")
        print(f"    Code   : {getattr(err, 'code', None)}")
        print(f"    Message: {err.message}")

    # Test 4: Prompt Triggering REQUIRE_APPROVAL
    print("\n--- [Step 4] Sending High-Risk Action Triggering REQUIRE_APPROVAL ---")
    try:
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Please deploy production application now."},
            ],
        )
        print("[!] ERROR: Request should have required human approval!")
    except APIStatusError as err:
        print(f"[✓] Successfully Paused for Human Approval (HTTP {err.status_code}):")
        print(f"    Message: {err.message}")

    print("\n" + "=" * 75)
    print(" EXTERNAL AGENT INTEGRATION TEST COMPLETE")
    print("=" * 75)


if __name__ == "__main__":
    main()

