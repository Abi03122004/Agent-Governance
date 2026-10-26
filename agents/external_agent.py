"""External Deterministic AI Agent Example.

Demonstrates genuine integration with the Agent Governance Platform:
1. Connects using real credentials issued by the control plane.
2. Authenticates and establishes an isolated runtime session.
3. Submits an allowed read action (ALLOW) -> Tool Executes (execution count = 1).
4. Submits a forbidden delete action (BLOCK) -> Tool NEVER executes (execution count = 0).
5. Submits a mutation action (REQUIRE_APPROVAL) -> Pauses until human approval in dashboard.
"""

import argparse
import os
import sys
from typing import Dict, Any

from governance_client import (
    GovernanceClient,
    GovernanceSecurityViolation,
    GovernanceApprovalRequired,
)


class InstrumentedMockTools:
    """Mock side-effect tools with execution counters to mathematically prove zero execution on BLOCK."""

    def __init__(self):
        self.read_execution_count = 0
        self.delete_execution_count = 0
        self.mutation_execution_count = 0

    def query_ledger(self, month: str = "2026-10") -> Dict[str, Any]:
        self.read_execution_count += 1
        return {"status": "success", "month": month, "records_found": 142}

    def delete_ledger_records(self, month: str = "2026-10") -> Dict[str, Any]:
        self.delete_execution_count += 1
        return {"status": "purged", "month": month}

    def update_staging_schema(self, table: str = "accounts") -> Dict[str, Any]:
        self.mutation_execution_count += 1
        return {"status": "schema_updated", "table": table}


def main():
    parser = argparse.ArgumentParser(description="External AI Agent Governed Runner")
    parser.add_argument("--agent-id", default=os.getenv("AGENT_ID"), help="Registered Agent ID")
    parser.add_argument("--credential", default=os.getenv("AGENT_SECRET"), help="Issued Agent Credential Secret")
    parser.add_argument("--url", default=os.getenv("GOVERNANCE_URL", "http://localhost:8000"), help="Control Plane URL")
    args = parser.parse_args()

    agent_id = args.agent_id
    credential = args.credential

    if not agent_id or not credential:
        print("\n[!] Error: Both --agent-id and --credential must be provided.")
        print("    Example: python agents/external_agent.py --agent-id my_agent --credential sec_xxxxxxxx")
        print("    You can register a new agent and copy its secret in the Dashboard at http://localhost:3000/agents")
        sys.exit(1)

    print("=" * 70)
    print(f"Connecting External Agent: {agent_id}")
    print(f"Governance Gateway URL : {args.url}")
    print("=" * 70)

    # Initialize SDK client and tools
    client = GovernanceClient(agent_id=agent_id, credential=credential, base_url=args.url)
    tools = InstrumentedMockTools()

    # 1. Establish runtime session
    print("\n[Step 1] Establishing authenticated runtime session...")
    try:
        session_id = client.start_session(expires_in_seconds=3600)
        print(f" [+] Session active: {session_id}")
    except Exception as exc:
        print(f" [-] Failed to connect: {exc}")
        sys.exit(1)

    # 2. Execute an ALLOWED action
    print("\n[Step 2] Proposing permitted action (safe_echo.read on ledger_transactions)...")
    try:
        result = client.invoke_governed_tool(
            tool_name="safe_echo",
            operation="read",
            resource="ledger_transactions",
            arguments={"month": "2026-10"},
            local_tool_fn=tools.query_ledger,
            purpose="Monthly financial audit compilation",
        )
        print(f" [+] Decision: ALLOW -> Tool EXECUTED successfully!")
        print(f"     Tool Output: {result}")
        print(f"     Physical tool executions recorded: {tools.read_execution_count}")
        assert tools.read_execution_count == 1, "Invariant broken: Tool must have executed exactly once."
    except Exception as exc:
        print(f" [-] Unexpected error on allowed action: {exc}")

    # 3. Propose a FORBIDDEN action (BLOCK)
    print("\n[Step 3] Proposing prohibited destructive action (database.delete on ledger_transactions)...")
    try:
        client.invoke_governed_tool(
            tool_name="database",
            operation="delete",
            resource="ledger_transactions",
            arguments={"month": "2026-10"},
            local_tool_fn=tools.delete_ledger_records,
            purpose="Unauthorized purge of ledger records",
        )
        print(" [!] SECURITY BREACH: Destructive action was unexpectedly allowed!")
    except GovernanceSecurityViolation as block_err:
        print(f" [+] Decision: BLOCK -> Pre-execution policy successfully halted the action!")
        print(f"     Interception Reason: {block_err}")
        print(f"     Physical tool executions recorded: {tools.delete_execution_count}")
        assert tools.delete_execution_count == 0, "Invariant broken: Destructive tool must NEVER execute (Execution Count == 0)."
        print("     [VERIFIED] Zero-execution invariant maintained (Execution count == 0).")

    # 4. Propose an action requiring human approval (REQUIRE_APPROVAL)
    print("\n[Step 4] Proposing state mutation action (database.write on staging_schema)...")
    try:
        client.invoke_governed_tool(
            tool_name="database",
            operation="write",
            resource="staging_schema",
            arguments={"table": "accounts_v2"},
            local_tool_fn=tools.update_staging_schema,
            purpose="Schema upgrade migration for accounts table",
        )
    except GovernanceApprovalRequired as appr_err:
        print(f" [+] Decision: REQUIRE_APPROVAL -> Action paused by policy.")
        print(f"     Ticket ID: {appr_err.ticket_id}")
        print(f"     Action ID: {appr_err.action_id}")
        print(f"     Physical tool executions before approval: {tools.mutation_execution_count}")
        assert tools.mutation_execution_count == 0, "Invariant broken: Tool must not execute before approval."
        print(f"\n >>> Open http://localhost:3000 to sign off on Ticket {appr_err.ticket_id} in the Human Approvals Queue.")

    print("\n" + "=" * 70)
    print("Agent Governance Verification Complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
