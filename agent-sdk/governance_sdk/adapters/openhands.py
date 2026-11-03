"""OpenHands Runtime Governance Adapter.

Allows OpenHands autonomous coding agents to enforce centralized security governance,
human approval workflows, tenant isolation, and cryptographic audit logging on all
tool executions (terminal bash commands, file I/O, file editing, browser, and IPython).
"""

import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from governance_sdk.client import GovernanceClient
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRequiredError,
    ApprovalTimeoutError,
    AuthenticationError,
    GatewayConnectionError,
    GovernanceError,
    PolicyBlockedError,
)
from governance_sdk.models import ActionDecision, EvaluationResult


def infer_openhands_action_semantics(action: Any) -> Tuple[str, str, str, Dict[str, Any]]:
    """Normalizes an OpenHands Action into canonical (tool, operation, resource, arguments).
    
    Supports:
    - CmdRunAction -> tool: 'shell', op: 'delete'/'write'/'read'/'execute', res: command
    - FileReadAction -> tool: 'filesystem', op: 'read', res: path
    - FileWriteAction -> tool: 'filesystem', op: 'write', res: path
    - FileEditAction -> tool: 'filesystem', op: 'write', res: path
    - BrowseURLAction -> tool: 'http', op: 'read', res: url
    - BrowseInteractiveAction -> tool: 'http', op: 'execute', res: actions
    - IPythonRunCellAction -> tool: 'ipython', op: 'execute', res: code snippet
    - MCPAction -> tool: 'mcp:<server>:<tool>', op: 'execute', res: tool_name
    """
    action_type = getattr(action, "action", "").lower()
    if not action_type:
        action_type = type(action).__name__.lower().replace("action", "")

    # 1. Shell commands
    if action_type in ("run", "cmd_run", "cmdrun"):
        cmd = str(getattr(action, "command", "") or "")
        cmd_lower = cmd.lower()
        if any(d in cmd_lower for d in ["rm -rf", "drop table", "shutdown", "mkfs", "dd if=", "kill -9", "truncate"]):
            op = "delete"
        elif any(w in cmd_lower for w in ["mkdir", "touch", "curl -o", "wget", "git clone", "pip install", "npm install", "yarn add"]):
            op = "write"
        elif any(r in cmd_lower for r in ["cat", "ls", "find", "grep", "head", "tail", "echo", "pwd", "whoami"]):
            op = "read"
        else:
            op = "execute"
        return "shell", op, cmd, {"command": cmd, "is_static": getattr(action, "is_static", False)}

    # 2. File Read
    if action_type in ("read", "file_read", "fileread"):
        path = str(getattr(action, "path", "") or "")
        view_range = getattr(action, "view_range", None)
        return "filesystem", "read", path, {"path": path, "view_range": view_range}

    # 3. File Write
    if action_type in ("write", "file_write", "filewrite"):
        path = str(getattr(action, "path", "") or "")
        content = getattr(action, "content", "") or ""
        return "filesystem", "write", path, {"path": path, "content_length": len(content)}

    # 4. File Edit
    if action_type in ("edit", "file_edit", "fileedit"):
        path = str(getattr(action, "path", "") or "")
        cmd = getattr(action, "command", "edit")
        old_str = getattr(action, "old_str", None)
        new_str = getattr(action, "new_str", None)
        return "filesystem", "write", path, {"path": path, "command": cmd, "has_replacement": bool(new_str)}

    # 5. Browser URL
    if action_type in ("browse", "browse_url", "browseurl"):
        url = str(getattr(action, "url", "") or "")
        return "http", "read", url, {"url": url}

    # 6. Browser Interactive
    if action_type in ("browse_interactive", "browseinteractive"):
        b_act = str(getattr(action, "browser_actions", "") or "")
        return "http", "execute", b_act[:256], {"browser_actions": b_act}

    # 7. IPython Code execution
    if action_type in ("run_ipython", "ipython_run_cell", "ipythonruncell"):
        code = str(getattr(action, "code", "") or "")
        return "ipython", "execute", code[:200], {"code": code}

    # 8. MCP Action
    if "mcp" in action_type:
        server = getattr(action, "server_name", "default")
        t_name = getattr(action, "tool_name", "tool")
        args = getattr(action, "arguments", {}) or {}
        return f"mcp:{server}:{t_name}", "execute", str(t_name), args

    # Default fallback
    resource = str(getattr(action, "path", None) or getattr(action, "command", None) or action_type)
    return "other", action_type, resource, {"raw": str(action)}


class OpenHandsGovernanceAdapter:
    """Governance mediation adapter tailored for OpenHands runtime lifecycle."""

    def __init__(
        self,
        client: GovernanceClient,
        auto_wait_approval: bool = True,
        approval_timeout: float = 60.0,
        fail_closed: bool = True,
    ):
        self.client = client
        self.auto_wait_approval = auto_wait_approval
        self.approval_timeout = approval_timeout
        self.fail_closed = fail_closed
        self._suspended = False

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    def is_governed_action(self, action: Any) -> bool:
        """Determines if the action causes runtime side-effects requiring governance."""
        action_name = getattr(action, "action", "")
        if not action_name:
            action_name = type(action).__name__.lower().replace("action", "")
        
        non_governed = {
            "think",
            "agentthink",
            "message",
            "agentmessage",
            "finish",
            "agentfinish",
            "null",
            "reject",
            "userreject",
            "task_tracking",
            "empty",
            "",
        }
        return action_name.lower() not in non_governed

    def mediate_and_execute(
        self,
        action: Any,
        execute_fn: Callable[[Any], Any],
        observation_factory: Optional[Callable[[str, Optional[str]], Any]] = None,
    ) -> Any:
        """Full mediation lifecycle intercepting the action before execution.
        
        If allowed:
        1. Pre-execution evaluation via Gateway
        2. Policy check: ALLOW, BLOCK, REQUIRE_APPROVAL, SUSPEND
        3. Pre-execution authorization check (/execute)
        4. Invokes execute_fn(action)
        5. Reports outcome to audit ledger (/result)
        6. Returns observation
        """
        # Quick-exit if not a governed action
        if not self.is_governed_action(action):
            return execute_fn(action)

        action_name = getattr(action, "action", type(action).__name__)

        # 1. Suspended Tripwire
        if self._suspended:
            err_msg = f"Governance Security TRIPWIRE: Agent SUSPENDED. Action '{action_name}' halted."
            return self._build_error_observation(err_msg, "AGENT_SUSPENDED", observation_factory)

        # 2. Extract normalized semantics
        tool, op, res, args = infer_openhands_action_semantics(action)
        thought = str(getattr(action, "thought", "") or f"OpenHands execution of {action_name}")

        # 3. Evaluate Action via Gateway
        try:
            eval_result: EvaluationResult = self.client.evaluate_action(
                tool=tool,
                operation=op,
                resource=res,
                arguments=args,
                action_description=thought[:500],
            )
        except AgentSuspendedError as exc:
            self._suspended = True
            err_msg = f"Governance Security TRIPWIRE: Agent SUSPENDED. Action '{action_name}' halted: {exc.message}"
            return self._build_error_observation(err_msg, "AGENT_SUSPENDED", observation_factory)
        except AuthenticationError as exc:
            err_msg = f"Governance Authentication Failed: {exc.message}"
            return self._build_error_observation(err_msg, "AUTHENTICATION_FAILED", observation_factory)
        except GatewayConnectionError as exc:
            if self.fail_closed:
                err_msg = f"Governance Gateway Unavailable (fail-closed): {exc.message}"
                return self._build_error_observation(err_msg, "GATEWAY_UNAVAILABLE", observation_factory)
            return execute_fn(action)
        except Exception as exc:
            if self.fail_closed:
                err_msg = f"Governance Mediation Exception (fail-closed): {str(exc)}"
                return self._build_error_observation(err_msg, "GOVERNANCE_ERROR", observation_factory)
            return execute_fn(action)

        # 4. Handle Policy Decisions
        if eval_result.is_suspended:
            self._suspended = True
            err_msg = f"Governance Security TRIPWIRE: Agent SUSPENDED. Action halted: {eval_result.explanation}"
            return self._build_error_observation(err_msg, eval_result.reason_code or "AGENT_SUSPENDED", observation_factory)

        if eval_result.is_blocked:
            err_msg = f"Governance Policy Blocked Action [{eval_result.reason_code}]: {eval_result.explanation}"
            return self._build_error_observation(err_msg, eval_result.reason_code, observation_factory)

        auth_token = eval_result.execution_authorization

        if eval_result.requires_approval:
            ticket_id = eval_result.approval_ticket_id or ""
            if not self.auto_wait_approval:
                err_msg = f"Governance Action Paused: Requires human operator approval (ticket: {ticket_id})"
                return self._build_error_observation(err_msg, "APPROVAL_REQUIRED", observation_factory)

            try:
                auth_token = self.client.wait_for_approval(
                    ticket_id=ticket_id,
                    timeout=self.approval_timeout,
                    poll_interval=1.5,
                )
            except (ApprovalTimeoutError, GovernanceError) as exc:
                err_msg = f"Governance Action Rejected: Human approval ticket '{ticket_id}' timed out or rejected: {str(exc)}"
                return self._build_error_observation(err_msg, "APPROVAL_TIMEOUT", observation_factory)

        if not auth_token:
            return self._build_error_observation(
                "Governance authorization missing; action halted.",
                "MISSING_AUTHORIZATION_TOKEN",
                observation_factory,
            )
        try:
            self.client.claim_execution(eval_result.action_id, auth_token)
        except Exception as exc:
            return self._build_error_observation(
                f"Governance authorization claim failed (fail-closed): {str(exc)}",
                "EXECUTION_CLAIM_FAILED",
                observation_factory,
            )

        # 5. Execute Underlying Tool
        obs = None
        exec_status = "succeeded"
        try:
            obs = execute_fn(action)
            # Detect error observations
            obs_type = type(obs).__name__
            if "Error" in obs_type or getattr(obs, "error", False):
                exec_status = "failed"
            return obs
        except Exception as exc:
            exec_status = "failed"
            err_msg = f"Tool execution failed: {str(exc)}"
            obs = self._build_error_observation(err_msg, "EXECUTION_EXCEPTION", observation_factory)
            return obs
        finally:
            # 6. Report Outcome & Redeem Single-Use Authorization Token in Cryptographic Audit Ledger
            if auth_token and eval_result.action_id:
                try:
                    obs_content = getattr(obs, "content", str(obs)) if obs else ""
                    self.client.report_result(
                        action_id=eval_result.action_id,
                        execution_authorization=auth_token,
                        status=exec_status,
                        output={"observation": str(obs_content)[:2048]},
                    )
                except Exception as exc:
                    # The side effect has happened but its terminal outcome is
                    # unknown to the gateway; surface this rather than silently
                    # presenting the action as fully governed.
                    return self._build_error_observation(
                        f"Governance result reporting failed: {str(exc)}",
                        "RESULT_REPORT_FAILED",
                        observation_factory,
                    )

    def _build_error_observation(
        self,
        content: str,
        error_id: Optional[str] = None,
        factory: Optional[Callable[[str, Optional[str]], Any]] = None,
    ) -> Any:
        """Constructs an ErrorObservation compatible with OpenHands."""
        if factory is not None:
            try:
                return factory(content, error_id)
            except Exception:
                pass

        try:
            from openhands.events.observation import ErrorObservation
            return ErrorObservation(content=content, error_id=error_id or "GOVERNANCE_ERROR")
        except ImportError:
            # Fallback dict representation if OpenHands is not directly imported
            return {
                "observation": "error",
                "content": content,
                "error_id": error_id or "GOVERNANCE_ERROR",
            }
