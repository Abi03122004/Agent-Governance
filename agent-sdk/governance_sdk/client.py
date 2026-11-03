"""Governance Gateway Client for External Autonomous AI Agents."""

import os
import time
import uuid
from typing import Any, Dict, Optional
import httpx

from governance_sdk.authentication import AgentAuthenticator
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRejectedError,
    ApprovalRequiredError,
    ApprovalTimeoutError,
    AuthenticationError,
    ExecutionAuthorizationError,
    GatewayConnectionError,
    GovernanceError,
    SessionExpiredError,
    TenantIsolationError,
)
from governance_sdk.models import (
    ActionDecision,
    AgentSession,
    ApprovalTicket,
    EvaluationResult,
    ExecutionResult,
    RuntimeActionInput,
)


class GovernanceClient:
    """Official Python Client for the Agent Security & Runtime Governance Gateway."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        agent_token: Optional[str] = None,
        timeout: float = 30.0,
        auto_start_session: bool = True,
    ):
        raw_url = base_url or os.environ.get("GOVERNANCE_GATEWAY_URL") or "http://127.0.0.1:8000"
        self.base_url = raw_url.rstrip("/")
        self.authenticator = AgentAuthenticator(agent_token)
        self.timeout = timeout
        self._current_session: Optional[AgentSession] = None
        self._http_client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.authenticator.get_auth_headers(),
        )

        if auto_start_session:
            try:
                self.start_session()
            except Exception:
                # Deferred until first action if server is temporarily starting up
                pass

    @property
    def session_id(self) -> Optional[str]:
        return self._current_session.session_id if self._current_session else None

    def start_session(self, expires_in_seconds: Optional[int] = None) -> AgentSession:
        """Start an authenticated runtime session with the governance gateway."""
        params = {}
        if expires_in_seconds:
            params["expires_in_seconds"] = expires_in_seconds

        try:
            resp = self._http_client.post("/api/v1/runtime/sessions", params=params)
        except httpx.RequestError as exc:
            raise GatewayConnectionError(f"Failed to connect to Governance Gateway: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Agent token is invalid or revoked.")
        if resp.status_code == 403:
            detail = resp.json().get("detail", "")
            if "suspended" in detail.lower():
                raise AgentSuspendedError(detail)
            raise TenantIsolationError(detail)
        if resp.status_code != 201:
            raise GovernanceError(f"Failed to start runtime session: {resp.status_code} {resp.text}")

        data = resp.json()
        self._current_session = AgentSession(**data)
        return self._current_session

    def ensure_session(self) -> str:
        """Ensure an active session exists, starting one if needed."""
        if not self._current_session:
            self.start_session()
        return self._current_session.session_id  # type: ignore[union-attr]

    def evaluate_action(
        self,
        tool: str,
        operation: str,
        resource: str,
        arguments: Optional[Dict[str, Any]] = None,
        action_description: Optional[str] = None,
        execution_context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> EvaluationResult:
        """Submit an untrusted tool call to the gateway for pre-execution policy evaluation."""
        active_session = session_id or self.ensure_session()
        payload = RuntimeActionInput(
            session_id=active_session,
            tool=tool,
            operation=operation,
            resource=resource,
            arguments=arguments or {},
            action_description=action_description,
            execution_context=execution_context or {},
            request_id=request_id or f"req_{uuid.uuid4().hex[:16]}",
        )

        try:
            resp = self._http_client.post("/api/v1/runtime/actions/evaluate", json=payload.model_dump(exclude_none=True))
        except httpx.RequestError as exc:
            raise GatewayConnectionError(f"Failed to connect to Governance Gateway: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Agent token is invalid or revoked.")
        if resp.status_code == 403:
            detail = resp.json().get("detail", "")
            if "identity mismatch" in detail.lower() or "tenant mismatch" in detail.lower():
                raise TenantIsolationError(detail)
            if "suspended" in detail.lower():
                raise AgentSuspendedError(detail)
            if "session expired" in detail.lower():
                raise SessionExpiredError(detail)
            raise GovernanceError(f"Evaluation forbidden: {detail}")
        if resp.status_code != 200:
            raise GovernanceError(f"Gateway evaluation failed with HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        return EvaluationResult(**data)

    def check_approval(self, ticket_id: str) -> ApprovalTicket:
        """Query the current state of a pending human approval ticket."""
        try:
            resp = self._http_client.get(f"/api/v1/runtime/approvals/{ticket_id}")
        except httpx.RequestError as exc:
            raise GatewayConnectionError(f"Failed to connect to Governance Gateway: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Agent token is invalid or revoked.")
        if resp.status_code == 404:
            raise GovernanceError(f"Approval ticket '{ticket_id}' not found.")
        if resp.status_code != 200:
            raise GovernanceError(f"Failed to check approval status: {resp.status_code} {resp.text}")

        data = resp.json()
        return ApprovalTicket(
            ticket_id=ticket_id,
            status=data.get("status", "PENDING"),
            execution_authorization=data.get("execution_authorization"),
        )

    def wait_for_approval(
        self,
        ticket_id: str,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> str:
        """Poll gateway until human approval is decided, returning single-use execution token."""
        start = time.time()
        while time.time() - start < timeout:
            ticket = self.check_approval(ticket_id)
            if ticket.status == "APPROVED" and ticket.execution_authorization:
                return ticket.execution_authorization
            if ticket.status == "REJECTED":
                raise ApprovalRejectedError(ticket_id)
            time.sleep(poll_interval)
        raise ApprovalTimeoutError(ticket_id, timeout)

    def claim_execution(
        self,
        action_id: str,
        execution_authorization: str,
    ) -> ExecutionResult:
        """Claim authorization immediately before a local runtime side effect."""
        try:
            resp = self._http_client.post(
                f"/api/v1/runtime/actions/{action_id}/claim",
                json={"execution_authorization": execution_authorization},
            )
        except httpx.RequestError as exc:
            raise GatewayConnectionError(f"Failed to connect to Governance Gateway: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Agent token is invalid or revoked.")
        if resp.status_code == 403:
            detail = resp.json().get("detail", "")
            if "suspended" in detail.lower():
                raise AgentSuspendedError(detail)
            if "execution authorization" in detail.lower():
                raise ExecutionAuthorizationError(detail)
            raise GovernanceError(f"Execution forbidden: {detail}")
        if resp.status_code != 200:
            raise GovernanceError(f"Execution authorization claim failed with HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        return ExecutionResult(**data)

    def execute_action(
        self,
        action_id: str,
        execution_authorization: str,
    ) -> ExecutionResult:
        """Deprecated compatibility alias for :meth:`claim_execution`."""
        return self.claim_execution(action_id, execution_authorization)

    def report_result(
        self,
        action_id: str,
        execution_authorization: str,
        status: str,
        output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Report local tool execution result back to the gateway for inspection and audit."""
        try:
            resp = self._http_client.post(
                f"/api/v1/runtime/actions/{action_id}/result",
                json={
                    "execution_authorization": execution_authorization,
                    "status": "succeeded" if status.lower() in {"succeeded", "success", "executed"} else "failed",
                    "output": output,
                },
            )
        except httpx.RequestError as exc:
            raise GatewayConnectionError(f"Failed to connect to Governance Gateway: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Agent token is invalid or revoked.")
        if resp.status_code != 200:
            raise GovernanceError(f"Failed to report result: {resp.status_code} {resp.text}")

        return resp.json()

    def close(self):
        """Close the underlying HTTP transport client."""
        self._http_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

