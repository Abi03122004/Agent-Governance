#!/usr/bin/env python3
"""Example: Independent LangGraph Agent Governed by the Centralized Gateway.

This script demonstrates an external LangGraph agent running as an independent process.
All tool executions are evaluated, mediated, and audited by the Governance Gateway.
"""

import os
import sys

# Ensure governance_sdk is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from governance_sdk import GovernanceClient
from governance_sdk.adapters.langgraph import wrap_tools
from governance_sdk.exceptions import PolicyBlockedError, AgentSuspendedError, ApprovalRequiredError


# 1. Define standard Python tool functions
def get_weather(city: str) -> str:
    """Fetch current weather report for a given city."""
    return f"Weather in {city}: 18°C, Partly Cloudy."


def delete_user_account(user_id: str) -> str:
    """Delete a user account from database (DESTRUCTIVE - BLOCKED)."""
    return f"User {user_id} deleted."


def deploy_production_service(service_name: str) -> str:
    """Deploy service to production environment (MUTATION - REQUIRES APPROVAL)."""
    return f"Service {service_name} deployed successfully to production."


def main():
    gateway_url = os.environ.get("GOVERNANCE_GATEWAY_URL", "http://127.0.0.1:8000")
    agent_token = os.environ.get("GOVERNANCE_AGENT_TOKEN", "agt_demo_token")

    print("=" * 70)
    print(" INDEPENDENT LANGGRAPH AGENT RUNTIME GOVERNANCE DEMO")
    print("=" * 70)
    print(f"[*] Gateway URL: {gateway_url}")
    print(f"[*] Agent Token: {agent_token[:10]}...")

    # Initialize client
    client = GovernanceClient(base_url=gateway_url, agent_token=agent_token, auto_start_session=True)
    print(f"[*] Governed Session ID: {client.session_id}")

    # Wrap raw tools using the LangGraph adapter
    tools = wrap_tools(
        [get_weather, delete_user_account, deploy_production_service],
        client=client,
        auto_wait_approval=False,
    )
    weather_tool, delete_tool, deploy_tool = tools

    # Action 1: ALLOW (Harmless read)
    print("\n--- [Action 1] Calling ALLOW tool (get_weather) ---")
    try:
        res = weather_tool.invoke({"city": "Tokyo"})
        print(f"[PASS] Tool executed: {res}")
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")

    # Action 2: BLOCK (Destructive operation)
    print("\n--- [Action 2] Calling BLOCK tool (delete_user_account) ---")
    try:
        delete_tool.invoke({"user_id": "usr_999"})
        print("[FAIL] Destructive tool executed without block!")
    except PolicyBlockedError as e:
        print(f"[PASS] Successfully BLOCKED by Gateway: {e.message}")

    # Action 3: REQUIRE_APPROVAL (Production deployment)
    print("\n--- [Action 3] Calling REQUIRE_APPROVAL tool (deploy_production_service) ---")
    try:
        deploy_tool.invoke({"service_name": "payments-api"})
        print("[FAIL] High-risk tool executed without approval!")
    except ApprovalRequiredError as e:
        print(f"[PASS] Successfully PAUSED by Gateway for approval: ticket={e.ticket_id}")

    client.close()
    print("\n" + "=" * 70)
    print(" DEMO COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()

