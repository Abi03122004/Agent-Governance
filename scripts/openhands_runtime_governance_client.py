"""OpenHands AI Agent Runtime Governance Client.

Provides fail-closed mediation for OpenHands actions through the Autonomous
AI Agent Runtime Governance Gateway.
"""

from dataclasses import dataclass, field
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also load from OpenHands parent folder if present
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except Exception:
    pass

logger = logging.getLogger(__name__)


@dataclass
class MediationDecision:
    decision: str  # ALLOW, BLOCK, REQUIRE_APPROVAL, SUSPEND
    action_id: str = ""
    execution_authorization: Optional[str] = None
    reason_code: str = ""
    explanation: str = ""
    risk_signals: List[str] = field(default_factory=list)
    approval_ticket_id: Optional[str] = None


class GovernanceClient:
    """Fail-closed governance mediation client for OpenHands runtime."""

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
        poll_timeout: Optional[float] = None,
    ):
        default_gw = "http://host.docker.internal:8000" if os.path.exists("/.dockerenv") else "http://localhost:8000"
        configured_gw = gateway_url or os.getenv("GOVERNANCE_GATEWAY_URL") or default_gw
        # If running inside a container and configured with localhost/127.0.0.1, rewrite to host.docker.internal
        if os.path.exists("/.dockerenv") and any(h in configured_gw for h in ("localhost", "127.0.0.1")):
            configured_gw = configured_gw.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
        self.gateway_url = configured_gw.rstrip("/")
        raw_key = api_key or os.getenv("GOVERNANCE_API_KEY") or ""
        self.api_key = raw_key.strip().lstrip("<").rstrip(">")
        self.timeout = float(timeout or os.getenv("GOVERNANCE_REQUEST_TIMEOUT_SECONDS", "5.0"))
        self.poll_interval = float(
            poll_interval or os.getenv("GOVERNANCE_APPROVAL_POLL_INTERVAL_SECONDS", "2.0")
        )
        self.poll_timeout = float(
            poll_timeout or os.getenv("GOVERNANCE_APPROVAL_TIMEOUT_SECONDS", "60.0")
        )

        self.session_id: Optional[str] = None
        self._suspended = False

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.gateway_url)

    def _headers(self, correlation_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def _request_with_retry(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[requests.Response]:
        """Send HTTP request with at most 1 retry on network error."""
        url = f"{self.gateway_url}{path}"
        headers = self._headers(correlation_id)

        for attempt in range(2):
            try:
                resp = requests.request(
                    method=method,
                    url=url,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout,
                )
                return resp
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == 1:
                    logger.warning("Governance gateway unreachable after retry: %s", type(exc).__name__)
                    return None
                time.sleep(0.5)
            except Exception as exc:
                logger.warning("Governance request error: %s", type(exc).__name__)
                return None
        return None

    def start_session(self, force_new: bool = False) -> Optional[str]:
        """Start an isolated runtime session once per agent run; cache session_id."""
        if self.session_id and not force_new:
            return self.session_id

        if not self.is_configured:
            return None

        resp = self._request_with_retry("POST", "/api/v1/runtime/sessions")
        if resp is not None and resp.status_code == 201:
            try:
                data = resp.json()
                self.session_id = data.get("session_id")
                return self.session_id
            except Exception:
                pass
        return None

    def is_governed_action(self, action: Any) -> bool:
        """Determines if the action is a side-effect action that must be mediated."""
        action_name = getattr(action, "action", "")
        # Non-side-effect actions to skip
        skip_actions = {
            "think",
            "message",
            "finish",
            "null",
            "reject",
            "task_tracking",
            "empty",
            "",
        }
        return action_name.lower() not in skip_actions

    def map_action(self, action: Any) -> Dict[str, Any]:
        """Map OpenHands Action object to RuntimeActionInput dictionary."""
        action_type = getattr(action, "action", "other").lower()
        purpose = getattr(action, "thought", "") or getattr(action, "purpose", None) or "OpenHands action execution"

        # Shell command -> tool=shell, operation=execute, resource=<command>
        if action_type in ("run", "cmd_run"):
            cmd = getattr(action, "command", "")
            return {
                "tool": "shell",
                "operation": "execute",
                "resource": cmd,
                "arguments": {"command": cmd},
                "destination": None,
                "purpose": purpose[:512] if purpose else None,
            }

        # File actions -> tool=filesystem, operation=read|write|delete
        if action_type in ("read", "file_read"):
            path = getattr(action, "path", "")
            return {
                "tool": "filesystem",
                "operation": "read",
                "resource": path,
                "arguments": {"path": path},
                "destination": None,
                "purpose": purpose[:512] if purpose else None,
            }

        if action_type in ("write", "file_write"):
            path = getattr(action, "path", "")
            content = getattr(action, "content", "")
            return {
                "tool": "filesystem",
                "operation": "write",
                "resource": path,
                "arguments": {"path": path, "content_length": len(content or "")},
                "destination": None,
                "purpose": purpose[:512] if purpose else None,
            }

        if action_type in ("edit", "file_edit"):
            path = getattr(action, "path", "")
            return {
                "tool": "filesystem",
                "operation": "write",
                "resource": path,
                "arguments": {"path": path},
                "destination": None,
                "purpose": purpose[:512] if purpose else None,
            }

        # Browse / HTTP -> tool=http, operation=read|write, resource=<url>, destination=<host>
        if action_type in ("browse", "browse_url"):
            url = getattr(action, "url", "")
            host = urlparse(url).netloc if url else None
            return {
                "tool": "http",
                "operation": "read",
                "resource": url,
                "arguments": {"url": url},
                "destination": host,
                "purpose": purpose[:512] if purpose else None,
            }

        # IPython -> tool=ipython, operation=execute
        if action_type in ("run_ipython", "ipython_run_cell"):
            code = getattr(action, "code", "")
            return {
                "tool": "ipython",
                "operation": "execute",
                "resource": code[:200],
                "arguments": {"code": code},
                "destination": None,
                "purpose": purpose[:512] if purpose else None,
            }

        # Browse Interactive -> tool=http, operation=execute
        if action_type in ("browse_interactive", "browseinteractive"):
            b_act = str(getattr(action, "browser_actions", "") or "")
            return {
                "tool": "http",
                "operation": "execute",
                "resource": b_act[:256],
                "arguments": {"browser_actions": b_act},
                "destination": None,
                "purpose": purpose[:512] if purpose else None,
            }

        # MCP Action -> tool=mcp:<server>:<tool>, operation=execute
        if "mcp" in action_type:
            server = getattr(action, "server_name", "default")
            t_name = getattr(action, "tool_name", None) or getattr(action, "name", "tool")
            args = getattr(action, "arguments", {}) or {}
            return {
                "tool": f"mcp:{server}:{t_name}",
                "operation": "execute",
                "resource": str(t_name),
                "arguments": args if isinstance(args, dict) else {"raw": str(args)},
                "destination": str(server),
                "purpose": purpose[:512] if purpose else None,
            }

        # Unknown action types -> map to tool=other and let policy decide
        return {
            "tool": "other",
            "operation": action_type,
            "resource": str(getattr(action, "path", None) or getattr(action, "command", None) or action_type),
            "arguments": {"raw_action": str(action)},
            "destination": None,
            "purpose": purpose[:512] if purpose else None,
        }

    def mediate(self, action: Any, purpose: Optional[str] = None) -> MediationDecision:
        """Evaluate action pre-execution and validate execution authorization."""
        if self._suspended:
            return MediationDecision(
                decision="SUSPEND",
                reason_code="AGENT_SUSPENDED",
                explanation="Agent session is SUSPENDED. All actions are halted.",
            )

        if not self.is_configured:
            # If governance is not configured at all, allow transparent pass-through
            return MediationDecision(decision="ALLOW", reason_code="GOVERNANCE_DISABLED")

        session_id = self.start_session()
        if not session_id:
            return MediationDecision(
                decision="BLOCK",
                reason_code="SESSION_UNAVAILABLE",
                explanation="Failed to establish governance session with gateway (fail-closed).",
            )

        payload = self.map_action(action)
        payload["session_id"] = session_id
        if purpose:
            payload["purpose"] = purpose[:512]

        # 1. Pre-execution Evaluate Call
        resp = self._request_with_retry("POST", "/api/v1/runtime/actions/evaluate", json_body=payload)
        if resp is None or resp.status_code != 200:
            status_code = resp.status_code if resp else "NO_RESPONSE"
            return MediationDecision(
                decision="BLOCK",
                reason_code="GATEWAY_EVALUATION_FAILED",
                explanation=f"Governance gateway evaluation rejected request [HTTP {status_code}] (fail-closed).",
            )

        try:
            eval_data = resp.json()
        except Exception:
            return MediationDecision(
                decision="BLOCK",
                reason_code="INVALID_GATEWAY_RESPONSE",
                explanation="Malformed response from governance evaluation endpoint.",
            )

        decision = eval_data.get("decision", "BLOCK")
        action_id = eval_data.get("action_id", "")
        reason_code = eval_data.get("reason_code", "")
        explanation = eval_data.get("explanation", "")
        risk_signals = eval_data.get("risk_signals", [])
        token = eval_data.get("execution_authorization")
        ticket_id = eval_data.get("approval_ticket_id")

        if decision == "SUSPEND":
            self._suspended = True
            return MediationDecision(
                decision="SUSPEND",
                action_id=action_id,
                reason_code=reason_code,
                explanation=explanation,
                risk_signals=risk_signals,
            )

        if decision == "BLOCK":
            return MediationDecision(
                decision="BLOCK",
                action_id=action_id,
                reason_code=reason_code,
                explanation=explanation,
                risk_signals=risk_signals,
            )

        if decision == "REQUIRE_APPROVAL":
            if not ticket_id:
                return MediationDecision(
                    decision="BLOCK",
                    action_id=action_id,
                    reason_code="MISSING_APPROVAL_TICKET",
                    explanation="Gateway required approval but issued no ticket ID.",
                )

            # Poll for HITL approval
            token = self._poll_approval(ticket_id)
            if not token:
                return MediationDecision(
                    decision="BLOCK",
                    action_id=action_id,
                    reason_code="APPROVAL_REJECTED_OR_TIMEOUT",
                    explanation=f"Human-in-the-loop approval ticket {ticket_id} was rejected or timed out.",
                    approval_ticket_id=ticket_id,
                )
            decision = "ALLOW"

        if decision == "ALLOW":
            if not token:
                return MediationDecision(
                    decision="BLOCK",
                    action_id=action_id,
                    reason_code="MISSING_AUTHORIZATION_TOKEN",
                    explanation="Action allowed but no execution authorization token provided.",
                )

            # 2. Atomically claim the action immediately before the runtime's
            # local side effect. The gateway never executes a placeholder tool.
            exec_resp = self._request_with_retry(
                "POST",
                f"/api/v1/runtime/actions/{action_id}/claim",
                json_body={"execution_authorization": token},
            )
            if exec_resp is None or exec_resp.status_code != 200:
                err_detail = "Authorization rejected by execution broker"
                if exec_resp is not None:
                    try:
                        err_detail = exec_resp.json().get("detail", err_detail)
                    except Exception:
                        pass
                return MediationDecision(
                    decision="BLOCK",
                    action_id=action_id,
                    reason_code="EXECUTE_BROKER_REJECTED",
                    explanation=f"Execution broker rejected authorization: {err_detail}",
                )

            return MediationDecision(
                decision="ALLOW",
                action_id=action_id,
                execution_authorization=token,
                reason_code=reason_code,
                explanation=explanation,
                risk_signals=risk_signals,
                approval_ticket_id=ticket_id,
            )

        return MediationDecision(
            decision="BLOCK",
            action_id=action_id,
            reason_code="UNEXPECTED_DECISION",
            explanation=f"Unhandled governance decision: {decision}",
        )

    def _poll_approval(self, ticket_id: str) -> Optional[str]:
        """Poll the agent approval endpoint until resolved or timed out."""
        start_time = time.time()
        while time.time() - start_time < self.poll_timeout:
            resp = self._request_with_retry("GET", f"/api/v1/runtime/approvals/{ticket_id}")
            if resp is not None and resp.status_code == 200:
                try:
                    data = resp.json()
                    status = data.get("status")
                    if status == "APPROVED":
                        return data.get("execution_authorization")
                    elif status in ("REJECTED", "EXPIRED"):
                        logger.info("Approval ticket %s resolved as %s", ticket_id, status)
                        return None
                except Exception:
                    pass
            time.sleep(self.poll_interval)
        logger.warning("Approval polling timed out for ticket %s", ticket_id)
        return None

    def report_result(
        self,
        action_id: str,
        execution_authorization: str,
        status: str,
        output: Any,
    ) -> bool:
        """Report execution outcome to the audit ledger."""
        if not self.is_configured or not action_id or not execution_authorization:
            return False

        # Truncate and sanitize output
        cleaned_output: Dict[str, Any] = {}
        if isinstance(output, dict):
            for k, v in output.items():
                s = str(v)
                cleaned_output[str(k)] = s[:2048] if len(s) > 2048 else s
        else:
            cleaned_output["output"] = str(output)[:2048]

        resp = self._request_with_retry(
            "POST",
            f"/api/v1/runtime/actions/{action_id}/result",
            json_body={
                "execution_authorization": execution_authorization,
                "status": "succeeded" if status == "succeeded" else "failed",
                "output": cleaned_output,
            },
        )
        return resp is not None and resp.status_code == 200


_default_client: Optional[GovernanceClient] = None


def get_governance_client() -> GovernanceClient:
    global _default_client
    if _default_client is None:
        _default_client = GovernanceClient()
    return _default_client

