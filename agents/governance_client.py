"""Agent Governance Runtime Client SDK.

Provides a clean, provider-neutral integration client for autonomous AI agents
to authenticate, establish runtime sessions, and mediate all tool invocations
strictly through the pre-execution Governance Gateway.
"""

import os
import time
from typing import Any, Callable, Dict, Optional
import requests


class GovernanceSecurityViolation(Exception):
    """Raised when an action is blocked or prohibited by the Governance Gateway."""
    pass


class GovernanceApprovalRequired(Exception):
    """Raised when an action requires human review before execution."""
    def __init__(self, message: str, ticket_id: str, action_id: str):
        super().__init__(message)
        self.ticket_id = ticket_id
        self.action_id = action_id


class GovernanceClient:
    """Official client for connecting external AI agents to the Agent Governance Control Plane."""

    def __init__(
        self,
        agent_id: str,
        credential: str,
        base_url: Optional[str] = None,
        timeout: int = 15,
    ):
        self.agent_id = agent_id
        self.credential = credential
        self.base_url = (base_url or os.getenv("GOVERNANCE_URL", "http://localhost:8000")).rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._headers = {
            "Authorization": f"Bearer {self.credential}",
            "Content-Type": "application/json",
        }

    def start_session(self, expires_in_seconds: Optional[int] = 3600) -> str:
        """Establish a cryptographically authenticated runtime session."""
        url = f"{self.base_url}/api/v1/runtime/sessions"
        params = {"expires_in_seconds": expires_in_seconds} if expires_in_seconds else {}
        resp = requests.post(url, headers=self._headers, params=params, timeout=self.timeout)
        if resp.status_code != 201:
            raise RuntimeError(f"Failed to establish runtime session ({resp.status_code}): {resp.text}")
        data = resp.json()
        self.session_id = data["session_id"]
        return self.session_id

    def evaluate_action(
        self,
        tool: str,
        operation: str,
        resource: str,
        arguments: Optional[Dict[str, Any]] = None,
        purpose: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a pre-execution action proposal to the Governance Gateway.
        
        Returns the gateway decision dictionary (ALLOW, BLOCK, REQUIRE_APPROVAL, or SUSPEND).
        """
        if not self.session_id:
            self.start_session()

        url = f"{self.base_url}/api/v1/runtime/actions/evaluate"
        headers = dict(self._headers)
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        payload = {
            "session_id": self.session_id,
            "tool": tool,
            "operation": operation,
            "resource": resource,
            "arguments": arguments or {},
            "purpose": purpose or f"{self.agent_id} requesting {tool}.{operation}",
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Gateway evaluation failed ({resp.status_code}): {resp.text}")

        return resp.json()

    def execute_action(self, action_id: str, execution_authorization: str) -> Dict[str, Any]:
        """Execute an allowed action through the gateway using its single-use execution token."""
        url = f"{self.base_url}/api/v1/runtime/actions/{action_id}/execute"
        payload = {"execution_authorization": execution_authorization}
        resp = requests.post(url, headers=self._headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Tool execution failed ({resp.status_code}): {resp.text}")
        return resp.json()

    def report_result(
        self,
        action_id: str,
        execution_authorization: str,
        status: str,
        output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Report execution output back to the runtime gateway."""
        url = f"{self.base_url}/api/v1/runtime/actions/{action_id}/result"
        payload = {
            "execution_authorization": execution_authorization,
            "status": status,
            "output": output or {},
        }
        resp = requests.post(url, headers=self._headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Report result failed ({resp.status_code}): {resp.text}")
        return resp.json()

    def invoke_governed_tool(
        self,
        tool_name: str,
        operation: str,
        resource: str,
        arguments: Dict[str, Any],
        local_tool_fn: Optional[Callable[..., Any]] = None,
        purpose: Optional[str] = None,
    ) -> Any:
        """High-level helper: Mediates a tool call through the gateway.
        
        Guarantees that `local_tool_fn` is NEVER invoked if the gateway blocks the action.
        """
        decision = self.evaluate_action(
            tool=tool_name,
            operation=operation,
            resource=resource,
            arguments=arguments,
            purpose=purpose,
        )

        outcome = decision["decision"]
        action_id = decision["action_id"]

        if outcome == "BLOCK":
            raise GovernanceSecurityViolation(
                f"Action BLOCKED by policy [{decision.get('reason_code')}]: {decision.get('explanation')}"
            )

        if outcome == "SUSPEND":
            raise GovernanceSecurityViolation(
                f"Agent is SUSPENDED. Action halted by policy: {decision.get('explanation')}"
            )

        if outcome == "REQUIRE_APPROVAL":
            ticket_id = decision.get("approval_ticket_id") or ""
            raise GovernanceApprovalRequired(
                f"Action requires human approval. Ticket: {ticket_id}",
                ticket_id=ticket_id,
                action_id=action_id,
            )

        if outcome == "ALLOW":
            auth_token = decision["execution_authorization"]
            
            # Execute through gateway broker
            gateway_result = self.execute_action(action_id, auth_token)

            # If a physical local client tool is also registered, invoke it with the verified authorization
            if local_tool_fn:
                return local_tool_fn(**arguments)
            return gateway_result.get("result")

        raise RuntimeError(f"Unexpected governance decision: {outcome}")
