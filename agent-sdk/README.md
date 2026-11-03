# Autonomous AI Agent Security and Runtime Governance Python SDK

The official Python SDK for connecting autonomous AI agents (LangGraph, CrewAI, AutoGen, OpenHands, Custom) to the Centralized Agent Governance Gateway.

## Architectural Boundary & Security Model

```
External Agent Process                      Governance Gateway (:8000)
+-------------------------------+           +-------------------------------+
| LangGraph StateGraph / Agent  |           | Centralized Enforcement Point |
|                               |           |                               |
| Tool Invocation Request       |           | 1. Bearer Token Auth          |
|               |               |           |    (Tenant & Agent Identity)  |
|               v               |           |                               |
| GovernedLangGraphTool Wrapper | --------> | 2. Deterministic Policy Engine|
|                               |  Evaluate |    (ALLOW/BLOCK/APPROVAL)     |
| [ALLOW] -> Executes Function  | <-------- |                               |
| [BLOCK] -> Aborts Execution   |  Decision | 3. Single-Use Auth Token      |
| [APPROVAL] -> Waits/Pauses    |           |                               |
| [SUSPEND] -> Freezes Agent    |           | 4. Hash-Chained Audit Ledger  |
+-------------------------------+           +-------------------------------+
```

> [!IMPORTANT]
> **Security Boundary Notice**: SDK mediation acts as an **application-layer policy enforcement point**.
> SDK mediation alone cannot physically block an external process with unrestricted host or network access from making raw direct HTTP requests to internal networks.
> Complete zero-trust isolation requires pairing this SDK with upstream credential vaulting (never distributing provider keys) and infrastructure-level network egress restrictions (e.g. firewalls, Envoy sidecars, or VPC service controls).

---

## Installation

```bash
pip install ./agent-sdk
```

Or install with LangGraph support:
```bash
pip install "./agent-sdk[langgraph]"
```

---

## Quickstart: LangGraph Agent Integration

### 1. Configure Credentials

External agents require **only** their agent bearer token (`agt_...`) and the gateway base URL.
No upstream provider keys (OpenAI / Anthropic / Gemini) are stored in the agent's environment!

```bash
export GOVERNANCE_GATEWAY_URL="http://127.0.0.1:8000"
export GOVERNANCE_AGENT_TOKEN="agt_your_agent_token_here"
```

### 2. Wrap Existing Tools with Zero Logic Changes

```python
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from governance_sdk import GovernanceClient
from governance_sdk.adapters.langgraph import wrap_tools

# 1. Initialize Governance Client
client = GovernanceClient(
    base_url="http://127.0.0.1:8000",
    agent_token="agt_your_agent_token_here",
)

# 2. Define standard tools
def read_financial_report(year: int) -> str:
    """Reads approved quarterly financial disclosures."""
    return f"Report {year}: Revenue grew by 14%."

def drop_production_table(table_name: str) -> str:
    """Destructive database operation (BLOCKED by governance)."""
    return f"Dropped {table_name}"

def deploy_to_production(version: str) -> str:
    """High-risk production deployment (REQUIRES HUMAN APPROVAL)."""
    return f"Deployed version {version} to production."

raw_tools = [read_financial_report, drop_production_table, deploy_to_production]

# 3. Wrap tools in one line - Reasoning logic is untouched!
governed_tools = wrap_tools(raw_tools, client=client, auto_wait_approval=True)

# 4. Mount into standard LangGraph ToolNode
tool_node = ToolNode(governed_tools)
```

---

## Decision Lifecycle

1. **ALLOW**:
   - Gateway verifies action against deterministic policy rules.
   - Issues a short-lived, single-use HMAC authorization token.
   - The tool executes locally.
   - Execution output is reported back to the gateway for sanitization and tamper-evident audit logging.

2. **BLOCK**:
   - Prohibited or destructive operations (e.g. `DROP DATABASE`, secret extraction, unauthorized egress) are stopped at the gateway.
   - The wrapper raises `PolicyBlockedError`.
   - **The underlying tool function is NEVER executed.**

3. **REQUIRE_APPROVAL**:
   - High-risk operations (e.g. production deployments, schema mutations) create an `ApprovalRequestModel` ticket.
   - The execution is paused.
   - Authorized human operators review and approve/reject in the Dashboard (`/approvals`).
   - If approved, an execution token is granted and execution resumes safely.

4. **SUSPEND**:
   - If an agent or its tenant organization is suspended, all subsequent actions and session initiations fail immediately with `AgentSuspendedError`.

---

## Error Handling

```python
from governance_sdk.exceptions import (
    AuthenticationError,
    PolicyBlockedError,
    AgentSuspendedError,
    ApprovalRequiredError,
    ApprovalRejectedError,
)

try:
    result = governed_tool(location="London")
except PolicyBlockedError as e:
    print(f"Action blocked by policy: {e.explanation} (Code: {e.reason_code})")
except AgentSuspendedError:
    print("Agent identity is suspended.")
except ApprovalRequiredError as e:
    print(f"Action paused awaiting approval ticket: {e.ticket_id}")
except ApprovalRejectedError as e:
    print(f"Human reviewer rejected the request: {e.reason}")
except AuthenticationError:
    print("Agent token was revoked or expired.")
```

