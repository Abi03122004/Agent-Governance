"""CrewAI Runtime Governance Adapter.

Allows existing CrewAI agents and crews to enforce centralized security governance,
human approval workflows, tenant isolation, and cryptographic audit logging on all
tool executions via official CrewAI tool hooks (before_tool_call / after_tool_call).
"""

import functools
import os
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    from crewai.hooks import (
        ToolCallHookContext,
        register_after_tool_call_hook,
        register_before_tool_call_hook,
        unregister_after_tool_call_hook,
        unregister_before_tool_call_hook,
    )
    from crewai.hooks.dispatch import HookAborted
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False
    ToolCallHookContext = Any  # type: ignore[assignment,misc]

    class HookAborted(Exception):  # type: ignore[no-redef]
        """Fallback exception when crewai is not installed."""
        def __init__(self, reason: str = "", source: Any = None):
            super().__init__(reason)
            self.reason = reason
            self.source = source

    def register_before_tool_call_hook(*args: Any, **kwargs: Any) -> None:
        pass

    def unregister_before_tool_call_hook(*args: Any, **kwargs: Any) -> None:
        pass

    def register_after_tool_call_hook(*args: Any, **kwargs: Any) -> None:
        pass

    def unregister_after_tool_call_hook(*args: Any, **kwargs: Any) -> None:
        pass

from governance_sdk.client import GovernanceClient
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRejectedError,
    ApprovalRequiredError,
    ApprovalTimeoutError,
    AuthenticationError,
    GatewayConnectionError,
    GovernanceError,
    PolicyBlockedError,
    TenantIsolationError,
)
from governance_sdk.models import ActionDecision, EvaluationResult


def infer_crewai_action_semantics(
    tool_name: str,
    tool_input: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """Normalizes a CrewAI tool invocation into canonical (tool, operation, resource, arguments).

    Supports:
    - Shell/Bash execution -> tool: 'shell', op: 'delete'/'write'/'read'/'execute', res: command
    - Filesystem operations -> tool: 'filesystem', op: 'read'/'write'/'delete', res: path
    - Web / HTTP requests -> tool: 'http', op: 'read'/'execute', res: url
    - SQL / Database -> tool: 'database', op: 'read'/'write'/'delete', res: query/table
    - Generic tools -> tool: tool_name, op: inferred, res: inferred
    """
    raw_args = tool_input or {}
    args = dict(raw_args) if isinstance(raw_args, dict) else {"raw_input": str(raw_args)}
    name_lower = tool_name.lower().strip()

    # 1. Infer Tool Category
    if any(k in name_lower for k in ["bash", "shell", "terminal", "command", "exec_cmd", "run_cmd"]):
        tool_cat = "shell"
    elif any(k in name_lower for k in ["file", "directory", "dir", "path", "read_file", "write_file", "delete_file"]):
        tool_cat = "filesystem"
    elif any(k in name_lower for k in ["http", "web", "browse", "scrape", "fetch", "url", "curl", "get_page"]):
        tool_cat = "http"
    elif any(k in name_lower for k in ["sql", "query", "db", "database", "postgres", "sqlite"]):
        tool_cat = "database"
    else:
        tool_cat = tool_name

    # 2. Infer Operation
    # Check command contents or tool name for dangerous deletion
    combined_text = f"{name_lower} " + " ".join(str(v).lower() for v in args.values())
    if any(k in combined_text for k in ["rm -rf", "drop table", "drop database", "shutdown", "mkfs", "dd if=", "kill -9", "truncate"]):
        op = "delete"
    elif any(k in name_lower for k in ["delete", "drop", "destroy", "remove", "purge", "unlink"]):
        op = "delete"
    elif any(k in combined_text for k in ["mkdir", "touch", "curl -o", "wget", "git clone", "pip install", "npm install"]):
        op = "write"
    elif any(k in name_lower for k in ["write", "create", "insert", "update", "mutate", "edit", "append", "deploy", "patch"]):
        op = "write"
    elif any(k in combined_text for k in ["cat", "ls", "grep", "find", "head", "tail", "echo", "pwd", "whoami"]) or any(k in name_lower for k in ["read", "get", "fetch", "list", "query", "search", "scan", "find", "cat", "view", "browse"]):
        op = "read"
    elif any(k in name_lower for k in ["send", "post", "egress", "publish", "email"]):
        op = "send"
    else:
        op = "execute"

    # 3. Infer Resource
    res = "default"
    for candidate_key in [
        "path",
        "file_path",
        "filepath",
        "filename",
        "directory",
        "url",
        "command",
        "query",
        "table",
        "target",
        "resource",
        "destination",
    ]:
        if candidate_key in args and isinstance(args[candidate_key], str) and args[candidate_key].strip():
            res = args[candidate_key].strip()
            break

    if res == "default" and "code" in args and isinstance(args["code"], str) and args["code"].strip():
        res = args["code"].strip()[:128]
    elif res == "default" and "text" in args and isinstance(args["text"], str) and args["text"].strip():
        res = args["text"].strip()[:128]
    elif res == "default":
        res = tool_name

    return tool_cat, op, res, args


class CrewAIGovernanceHook:
    """Interception hook manager for CrewAI agents and crews.

    Registers as an official CrewAI before_tool_call and after_tool_call hook,
    validating every tool call against the centralized Governance Gateway.
    """

    def __init__(
        self,
        client: GovernanceClient,
        target_agent: Optional[Any] = None,
        target_crew: Optional[Any] = None,
        auto_wait_approval: bool = True,
        approval_timeout: float = 60.0,
        fail_closed: bool = True,
        on_blocked: Optional[Callable[[Any, str], None]] = None,
    ):
        self.client = client
        self.target_agent = target_agent
        self.target_crew = target_crew
        self.auto_wait_approval = auto_wait_approval
        self.approval_timeout = approval_timeout
        self.fail_closed = fail_closed
        self.on_blocked = on_blocked

        self._suspended = False
        self._registered = False
        self._pending_actions: Dict[int, Tuple[str, str]] = {}
        self._last_blocked_reason: Optional[str] = None

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    @property
    def is_registered(self) -> bool:
        return self._registered

    @property
    def last_blocked_reason(self) -> Optional[str]:
        return self._last_blocked_reason

    def _matches_target(self, context: Any) -> bool:
        """Determines if the hook context matches the scoped agent or crew."""
        if self.target_agent is not None:
            ctx_agent = getattr(context, "agent", None)
            if ctx_agent is not None:
                # Compare object identity or role
                same_id = ctx_agent is self.target_agent or id(ctx_agent) == id(self.target_agent)
                target_role = getattr(self.target_agent, "role", None)
                ctx_role = getattr(ctx_agent, "role", None)
                same_role = target_role is not None and target_role == ctx_role
                if not (same_id or same_role):
                    return False

        if self.target_crew is not None:
            ctx_crew = getattr(context, "crew", None)
            if ctx_crew is not None and ctx_crew is not self.target_crew and id(ctx_crew) != id(self.target_crew):
                return False

        return True

    def before_tool_call(self, context: Any) -> Optional[bool]:
        """Interception hook invoked before a CrewAI tool executes.

        Returns:
            None or True to permit tool execution.
            False to abort tool execution (CrewAI will block and never invoke the tool).
        """
        # 1. Target scope filtering: if not targeting this agent/crew, pass through
        if not self._matches_target(context):
            return None

        tool_name = getattr(context, "tool_name", "unknown_tool")
        tool_input = getattr(context, "tool_input", {}) or {}

        # 2. Suspended Tripwire
        if self._suspended:
            self._last_blocked_reason = "AGENT_SUSPENDED: Agent is suspended by security tripwire."
            if self.on_blocked:
                self.on_blocked(context, self._last_blocked_reason)
            return False

        # 3. Extract canonical action semantics
        tool_cat, op, res, args = infer_crewai_action_semantics(tool_name, tool_input)
        desc = f"CrewAI tool execution: {tool_name} on {res}"

        # 4. Evaluate action at Centralized Governance Gateway
        try:
            eval_result: EvaluationResult = self.client.evaluate_action(
                tool=tool_cat,
                operation=op,
                resource=res,
                arguments=args,
                action_description=desc,
            )
        except AgentSuspendedError as exc:
            self._suspended = True
            self._last_blocked_reason = f"AGENT_SUSPENDED: {exc.message}"
            if self.on_blocked:
                self.on_blocked(context, self._last_blocked_reason)
            return False
        except (AuthenticationError, TenantIsolationError) as exc:
            self._last_blocked_reason = f"AUTHENTICATION_FAILED: {exc.message}"
            if self.on_blocked:
                self.on_blocked(context, self._last_blocked_reason)
            return False if self.fail_closed else None
        except GatewayConnectionError as exc:
            self._last_blocked_reason = f"GATEWAY_UNAVAILABLE: {exc.message}"
            if self.on_blocked:
                self.on_blocked(context, self._last_blocked_reason)
            return False if self.fail_closed else None
        except Exception as exc:
            self._last_blocked_reason = f"GOVERNANCE_EXCEPTION: {str(exc)}"
            if self.on_blocked:
                self.on_blocked(context, self._last_blocked_reason)
            return False if self.fail_closed else None

        # 5. Handle Policy Decisions
        if eval_result.is_suspended:
            self._suspended = True
            self._last_blocked_reason = eval_result.reason_code or "AGENT_SUSPENDED"
            if self.on_blocked:
                self.on_blocked(context, self._last_blocked_reason)
            return False

        if eval_result.is_blocked:
            self._last_blocked_reason = eval_result.reason_code or "POLICY_BLOCKED"
            if self.on_blocked:
                self.on_blocked(context, self._last_blocked_reason)
            return False

        auth_token = eval_result.execution_authorization

        if eval_result.requires_approval:
            ticket_id = eval_result.approval_ticket_id or ""
            if not self.auto_wait_approval:
                self._last_blocked_reason = f"APPROVAL_REQUIRED: ticket {ticket_id}"
                if self.on_blocked:
                    self.on_blocked(context, self._last_blocked_reason)
                return False

            try:
                auth_token = self.client.wait_for_approval(
                    ticket_id=ticket_id,
                    timeout=self.approval_timeout,
                    poll_interval=1.0,
                )
            except (ApprovalTimeoutError, ApprovalRejectedError, GovernanceError) as exc:
                self._last_blocked_reason = f"APPROVAL_REJECTED_OR_TIMEOUT: {str(exc)}"
                if self.on_blocked:
                    self.on_blocked(context, self._last_blocked_reason)
                return False

        # Permitted action: track action ID and single-use auth token for after-hook audit logging
        if eval_result.action_id and auth_token:
            payload = (eval_result.action_id, auth_token)
            self._pending_actions[id(context)] = payload
            self._pending_actions[(threading.get_ident(), tool_name)] = payload

        return None  # Permitted: proceed to tool execution

    def after_tool_call(self, context: Any) -> Optional[str]:
        """Interception hook invoked after a CrewAI tool executes.

        Reports execution output to the gateway and redeems the single-use token
        into the tamper-evident hash-chained audit ledger.
        """
        # If not matching target scope, pass through
        if not self._matches_target(context):
            return None

        ctx_id = id(context)
        tool_name = getattr(context, "tool_name", "unknown_tool")
        thread_key = (threading.get_ident(), tool_name)

        action_data = None
        if ctx_id in self._pending_actions:
            action_data = self._pending_actions.pop(ctx_id)
            self._pending_actions.pop(thread_key, None)
        elif thread_key in self._pending_actions:
            action_data = self._pending_actions.pop(thread_key)
        elif self._pending_actions:
            last_key = next(reversed(list(self._pending_actions.keys())))
            action_data = self._pending_actions.pop(last_key)

        if action_data:
            action_id, auth_token = action_data
            raw_res = getattr(context, "raw_tool_result", None)
            tool_res = getattr(context, "tool_result", str(raw_res))

            # Detect failure
            is_err = "error" in str(tool_res).lower() or isinstance(raw_res, Exception)
            exec_status = "failed" if is_err else "succeeded"

            try:
                self.client.report_result(
                    action_id=action_id,
                    execution_authorization=auth_token,
                    status=exec_status,
                    output={"result": str(tool_res)[:2048]},
                )
            except Exception:
                # Telemetry / reporting errors must not disrupt runtime output
                pass

        return None

    def register(self) -> "CrewAIGovernanceHook":
        """Register hooks globally with CrewAI."""
        if not self._registered:
            register_before_tool_call_hook(self.before_tool_call)
            register_after_tool_call_hook(self.after_tool_call)
            self._registered = True
        return self

    def unregister(self) -> None:
        """Unregister hooks from CrewAI."""
        if self._registered:
            unregister_before_tool_call_hook(self.before_tool_call)
            unregister_after_tool_call_hook(self.after_tool_call)
            self._registered = False

    def __enter__(self) -> "CrewAIGovernanceHook":
        return self.register()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.unregister()


class GovernedCrewAITool:
    """Wrapper that adapts any CrewAI tool with direct governance mediation.

    Useful when targeting specific individual tools rather than global hooks.
    """

    def __init__(
        self,
        base_tool: Any,
        client: GovernanceClient,
        tool_name: Optional[str] = None,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        auto_wait_approval: bool = True,
        approval_timeout: float = 60.0,
        fail_closed: bool = True,
    ):
        self.base_tool = base_tool
        self.client = client
        self.explicit_operation = operation
        self.explicit_resource = resource
        self.auto_wait_approval = auto_wait_approval
        self.approval_timeout = approval_timeout
        self.fail_closed = fail_closed
        self._suspended = False

        self.name = tool_name or getattr(base_tool, "name", "governed_tool")
        self.description = getattr(base_tool, "description", "Governance mediated tool")
        self.args_schema = getattr(base_tool, "args_schema", None)

    def to_structured_tool(self) -> Any:
        """Converts to a CrewStructuredTool if supported."""
        if hasattr(self.base_tool, "to_structured_tool"):
            st = self.base_tool.to_structured_tool()
            # Wrap the invoke method
            orig_invoke = st.invoke
            orig_run = getattr(st, "run", None)

            def governed_run(*args: Any, **kwargs: Any) -> Any:
                return self.run(*args, **kwargs)

            st.invoke = governed_run
            if orig_run:
                st.run = governed_run
            return st
        return self

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Executes the tool through governance mediation."""
        if self._suspended:
            return "Tool execution blocked: Agent is SUSPENDED."

        # Flatten arguments
        tool_input = kwargs if kwargs else (args[0] if args and isinstance(args[0], dict) else {"args": args})
        tool_cat, op, res, parsed_args = infer_crewai_action_semantics(self.name, tool_input)

        if self.explicit_operation:
            op = self.explicit_operation
        if self.explicit_resource:
            res = self.explicit_resource

        try:
            eval_result = self.client.evaluate_action(
                tool=tool_cat,
                operation=op,
                resource=res,
                arguments=parsed_args,
                action_description=f"Governed tool execution: {self.name}",
            )
        except AgentSuspendedError:
            self._suspended = True
            return "Tool execution blocked: Agent is SUSPENDED."
        except Exception as exc:
            if self.fail_closed:
                return f"Tool execution blocked: Governance gateway unavailable ({exc})."
            # Fail open fallback if explicitly configured
            return self._call_base(*args, **kwargs)

        if eval_result.is_suspended:
            self._suspended = True
            return f"Tool execution blocked: Agent SUSPENDED ({eval_result.explanation})."

        if eval_result.is_blocked:
            return f"Tool execution blocked by hook. Tool: {self.name}"

        auth_token = eval_result.execution_authorization

        if eval_result.requires_approval:
            ticket_id = eval_result.approval_ticket_id or ""
            if not self.auto_wait_approval:
                return f"Tool execution paused: Requires human approval (ticket: {ticket_id})."
            try:
                auth_token = self.client.wait_for_approval(
                    ticket_id=ticket_id,
                    timeout=self.approval_timeout,
                    poll_interval=1.0,
                )
            except Exception as exc:
                return f"Tool execution blocked: Human approval failed ({exc})."

        # Execute
        status = "succeeded"
        result = None
        try:
            result = self._call_base(*args, **kwargs)
            return result
        except Exception as exc:
            status = "failed"
            result = str(exc)
            raise
        finally:
            if auth_token and eval_result.action_id:
                try:
                    self.client.report_result(
                        action_id=eval_result.action_id,
                        execution_authorization=auth_token,
                        status=status,
                        output={"result": str(result)[:2048]},
                    )
                except Exception:
                    pass

    def _call_base(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self.base_tool, "invoke"):
            # CrewStructuredTool / LangChain BaseTool style
            if args and isinstance(args[0], dict) and not kwargs:
                return self.base_tool.invoke(args[0])
            return self.base_tool.invoke(kwargs)
        if hasattr(self.base_tool, "run"):
            return self.base_tool.run(*args, **kwargs)
        if callable(self.base_tool):
            return self.base_tool(*args, **kwargs)
        raise ValueError(f"Underlying tool {self.base_tool} is not callable.")
