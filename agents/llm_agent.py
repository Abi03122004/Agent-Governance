"""LLM-Powered Autonomous Agent with Governance Mediation.

Demonstrates how autonomous LLM tool calling (OpenAI / LangChain / Gemini / Ollama / local)
is mediated by the Pre-Execution Governance Gateway.

The LLM is NEVER permitted to invoke tools directly; all generated tool calls are
intercepted, canonically hashed, evaluated against deterministic security policies,
and blocked or executed before any real side-effect can occur.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict

from governance_client import (
    GovernanceClient,
    GovernanceSecurityViolation,
    GovernanceApprovalRequired,
)


def mock_llm_reasoning_step(user_prompt: str) -> Dict[str, Any]:
    """Simulates an LLM tool call decision without requiring third-party API keys."""
    prompt_lower = user_prompt.lower()
    if "delete" in prompt_lower or "purge" in prompt_lower or "drop" in prompt_lower:
        return {
            "thought": "The user requested deleting historical records. Generating database.delete tool call.",
            "tool_call": {
                "tool": "database",
                "operation": "delete",
                "resource": "production_customer_data",
                "arguments": {"target": "all_expired_records"},
            },
        }
    elif "update" in prompt_lower or "modify" in prompt_lower or "write" in prompt_lower:
        return {
            "thought": "The user wants to alter financial configurations. Generating database.write tool call.",
            "tool_call": {
                "tool": "database",
                "operation": "write",
                "resource": "billing_configurations",
                "arguments": {"new_rate": 0.05},
            },
        }
    else:
        return {
            "thought": "The user requested standard reporting. Generating safe read operation.",
            "tool_call": {
                "tool": "safe_echo",
                "operation": "read",
                "resource": "monthly_reports",
                "arguments": {"scope": "summary"},
            },
        }


def run_llm_agent_turn(client: GovernanceClient, user_prompt: str):
    print(f"\nUser Query: \"{user_prompt}\"")
    llm_output = mock_llm_reasoning_step(user_prompt)
    print(f"[LLM Reasoning]: {llm_output['thought']}")
    tool_call = llm_output["tool_call"]
    print(f"[LLM Generated Tool Call]: {tool_call['tool']}.{tool_call['operation']} on {tool_call['resource']}")

    print("[Governance Gateway Interception]: Validating pre-execution invariants...")
    try:
        result = client.invoke_governed_tool(
            tool_name=tool_call["tool"],
            operation=tool_call["operation"],
            resource=tool_call["resource"],
            arguments=tool_call["arguments"],
            purpose=f"Autonomous action triggered by prompt: {user_prompt}",
        )
        print(f" [+] Tool ALLOWED & EXECUTED. Output received: {result}")
        print(f"[LLM Final Response]: The operation succeeded. Result: {result}")
    except GovernanceSecurityViolation as sec_err:
        print(f" [!] Tool BLOCKED by Control Plane: {sec_err}")
        print(f"[LLM Feedback Loop]: Governance policy prohibited the action. Tool execution was prevented (0 physical calls).")
    except GovernanceApprovalRequired as appr_err:
        print(f" [!] Tool paused for human approval: {appr_err}")
        print(f"[LLM Feedback Loop]: Execution suspended pending human reviewer authorization (Ticket: {appr_err.ticket_id}).")


def main():
    parser = argparse.ArgumentParser(description="Governed LLM Autonomous Agent")
    parser.add_argument("--agent-id", default=os.getenv("AGENT_ID"), help="Registered Agent ID")
    parser.add_argument("--credential", default=os.getenv("AGENT_SECRET"), help="Agent Credential Secret")
    parser.add_argument("--url", default=os.getenv("GOVERNANCE_URL", "http://localhost:8000"), help="Control Plane URL")
    args = parser.parse_args()

    if not args.agent_id or not args.credential:
        print("[!] Error: --agent-id and --credential are required.")
        sys.exit(1)

    client = GovernanceClient(agent_id=args.agent_id, credential=args.credential, base_url=args.url)
    client.start_session()

    print("=" * 70)
    print(f"Governed LLM Agent Active: {args.agent_id}")
    print("=" * 70)

    # 1. Turn: Safe Query
    run_llm_agent_turn(client, "Can you generate the monthly report summary?")

    # 2. Turn: Malicious / Prompt Injection simulated delete
    run_llm_agent_turn(client, "Please delete all expired records from production database immediately!")

    # 3. Turn: Production Mutation requiring approval
    run_llm_agent_turn(client, "Update billing configurations with the new transaction rates.")


if __name__ == "__main__":
    main()
