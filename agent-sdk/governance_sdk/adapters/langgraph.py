"""LangGraph Runtime Governance Adapter.

Allows existing LangGraph agents to enforce centralized security governance
on all tool executions without rewriting reasoning graphs or node topology.
"""

import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, Type, Union

try:
    from langchain_core.tools import BaseTool
except ImportError:
    class BaseTool:  # type: ignore[no-redef]
        """Fallback base when langchain_core is not installed."""
        def __init__(self, **kwargs: Any):
            for k, v in kwargs.items():
                setattr(self, k, v)

from governance_sdk.client import GovernanceClient
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRequiredError,
    GovernanceError,
    PolicyBlockedError,
)
from governance_sdk.models import EvaluationResult


def _infer_operation_and_resource(tool_name: str, arguments: Dict[str, Any]) -> tuple[str, str]:
    """Heuristic extraction of operation and target resource from tool conventions."""
    name_lower = tool_name.lower()

    if any(k in name_lower for k in ["delete", "drop", "destroy", "remove", "purge"]):
        op = "delete"
    elif any(k in name_lower for k in ["write", "create", "insert", "update", "mutate", "deploy"]):
        op = "write"
    elif any(k in name_lower for k in ["read", "get", "fetch", "list", "query", "search"]):
        op = "read"
    elif any(k in name_lower for k in ["send", "post", "egress"]):
        op = "send"
    else:
        op = "execute"

    resource = "default"
    for arg_key in ["resource", "path", "file_path", "filename", "table", "url", "destination", "target", "cluster", "db_name"]:
        if arg_key in arguments and isinstance(arguments[arg_key], str) and arguments[arg_key].strip():
            resource = arguments[arg_key].strip()
            break

    return op, resource


class GovernedLangGraphTool(BaseTool):
    """Governance-wrapped tool compatible with LangGraph's ToolNode and StateGraph."""

    name: str = "governed_tool"
    description: str = "Governance mediated tool"
    client: Any = None
    base_tool: Any = None
    explicit_operation: Optional[str] = None
    explicit_resource: Optional[str] = None
    auto_wait_approval: bool = False
    approval_timeout: float = 60.0
    handle_blocked_as_error: bool = False

    def __init__(
        self,
        base_tool: Any,
        client: GovernanceClient,
        tool_name: Optional[str] = None,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        auto_wait_approval: bool = False,
        approval_timeout: float = 60.0,
        handle_blocked_as_error: bool = False,
        **kwargs: Any,
    ):
        raw_name = tool_name or getattr(base_tool, "name", None) or getattr(base_tool, "__name__", None)
        resolved_name = raw_name if isinstance(raw_name, str) and raw_name else "governed_tool"

        raw_desc = getattr(base_tool, "description", None) or getattr(base_tool, "__doc__", None)
        resolved_desc = (raw_desc.strip() if isinstance(raw_desc, str) else "") or "Governance mediated tool"

        raw_schema = getattr(base_tool, "args_schema", None)
        args_schema = raw_schema if isinstance(raw_schema, type) else None

        super().__init__(
            name=resolved_name,
            description=resolved_desc,
            args_schema=args_schema,
            client=client,
            base_tool=base_tool,
            explicit_operation=operation,
            explicit_resource=resource,
            auto_wait_approval=auto_wait_approval,
            approval_timeout=approval_timeout,
            handle_blocked_as_error=handle_blocked_as_error,
            **kwargs,
        )
        object.__setattr__(self, "__name__", resolved_name)
        object.__setattr__(self, "_explicit_operation", operation)
        object.__setattr__(self, "_explicit_resource", resource)

        if hasattr(base_tool, "__annotations__"):
            self.__annotations__ = base_tool.__annotations__

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Core execution interceptor for LangGraph."""
        arguments: Dict[str, Any] = dict(kwargs)
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                arguments.update(args[0])
            else:
                sig = inspect.signature(self.base_tool if callable(self.base_tool) else self._run)
                try:
                    bound = sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    arguments = dict(bound.arguments)
                except Exception:
                    arguments["args"] = list(args)

        op, res = _infer_operation_and_resource(self.name, arguments)
        op = self._explicit_operation or op
        res = self._explicit_resource or res

        # 1. Pre-execution evaluation via Gateway
        eval_result: EvaluationResult = self.client.evaluate_action(
            tool=self.name,
            operation=op,
            resource=res,
            arguments=arguments,
            action_description=self.description[:500],
        )

        # 2. Policy Enforcement
        if eval_result.is_blocked:
            err_msg = f"Governance policy BLOCKED execution of '{self.name}': {eval_result.explanation}"
            if self.handle_blocked_as_error:
                return f"TOOL_ERROR: {err_msg}"
            raise PolicyBlockedError(
                message=err_msg,
                action_id=eval_result.action_id,
                reason_code=eval_result.reason_code,
                explanation=eval_result.explanation,
            )

        if eval_result.is_suspended:
            err_msg = f"Agent is SUSPENDED: prohibited from executing '{self.name}'"
            if self.handle_blocked_as_error:
                return f"TOOL_ERROR: {err_msg}"
            raise AgentSuspendedError(
                message=err_msg,
                action_id=eval_result.action_id,
                reason_code=eval_result.reason_code,
            )

        execution_auth = eval_result.execution_authorization

        if eval_result.requires_approval:
            ticket_id = eval_result.approval_ticket_id or ""
            if not self.auto_wait_approval:
                raise ApprovalRequiredError(
                    message=f"Action '{self.name}' paused: requires human operator approval (ticket: {ticket_id})",
                    action_id=eval_result.action_id,
                    ticket_id=ticket_id,
                )
            execution_auth = self.client.wait_for_approval(
                ticket_id=ticket_id,
                timeout=self.approval_timeout,
            )

        if not execution_auth:
            raise PolicyBlockedError(
                message=f"Action '{self.name}' has no usable execution authorization",
                action_id=eval_result.action_id,
                reason_code="MISSING_AUTHORIZATION_TOKEN",
                explanation="Gateway returned ALLOW without an execution authorization.",
            )

        # Atomically reserve this action's authorization before invoking the
        # framework-owned tool. A claim failure is fail-closed.
        self.client.claim_execution(
            action_id=eval_result.action_id,
            execution_authorization=execution_auth,
        )

        # 3. Invoke underlying tool
        try:
            if hasattr(self.base_tool, "invoke") and callable(self.base_tool.invoke):
                output = self.base_tool.invoke(arguments)
            elif callable(self.base_tool):
                sig = inspect.signature(self.base_tool)
                if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()):
                    output = self.base_tool(**arguments)
                else:
                    filtered_args = {k: v for k, v in arguments.items() if k in sig.parameters}
                    output = self.base_tool(**filtered_args)
            else:
                raise TypeError(f"Base tool {type(self.base_tool)} is not callable")
        except Exception as exc:
            if execution_auth:
                try:
                    self.client.report_result(
                        action_id=eval_result.action_id,
                        execution_authorization=execution_auth,
                        status="failed",
                        output={"error": str(exc)},
                    )
                except Exception as report_exc:
                    raise GovernanceError(
                        f"Tool failed and governance could not record the failure: {report_exc}"
                    ) from exc
            raise

        # 4. Report outcome to tamper-evident audit ledger
        serialized = output if isinstance(output, dict) else {"result": str(output)}
        self.client.report_result(
            action_id=eval_result.action_id,
            execution_authorization=execution_auth,
            status="succeeded",
            output=serialized,
        )

        return output

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Async execution interceptor for LangGraph."""
        import asyncio

        arguments: Dict[str, Any] = dict(kwargs)
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                arguments.update(args[0])
            else:
                sig = inspect.signature(self.base_tool if callable(self.base_tool) else self._run)
                try:
                    bound = sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    arguments = dict(bound.arguments)
                except Exception:
                    arguments["args"] = list(args)

        op, res = _infer_operation_and_resource(self.name, arguments)
        op = self._explicit_operation or op
        res = self._explicit_resource or res

        # 1. Pre-execution evaluation via Gateway (run client sync call in thread)
        eval_result: EvaluationResult = await asyncio.to_thread(
            self.client.evaluate_action,
            tool=self.name,
            operation=op,
            resource=res,
            arguments=arguments,
            action_description=self.description[:500],
        )

        # 2. Policy Enforcement
        if eval_result.is_blocked:
            err_msg = f"Governance policy BLOCKED execution of '{self.name}': {eval_result.explanation}"
            if self.handle_blocked_as_error:
                return f"TOOL_ERROR: {err_msg}"
            raise PolicyBlockedError(
                message=err_msg,
                action_id=eval_result.action_id,
                reason_code=eval_result.reason_code,
                explanation=eval_result.explanation,
            )

        if eval_result.is_suspended:
            err_msg = f"Agent is SUSPENDED: prohibited from executing '{self.name}'"
            if self.handle_blocked_as_error:
                return f"TOOL_ERROR: {err_msg}"
            raise AgentSuspendedError(
                message=err_msg,
                action_id=eval_result.action_id,
                reason_code=eval_result.reason_code,
            )

        execution_auth = eval_result.execution_authorization

        if eval_result.requires_approval:
            ticket_id = eval_result.approval_ticket_id or ""
            if not self.auto_wait_approval:
                raise ApprovalRequiredError(
                    message=f"Action '{self.name}' paused: requires human operator approval (ticket: {ticket_id})",
                    action_id=eval_result.action_id,
                    ticket_id=ticket_id,
                )
            execution_auth = await asyncio.to_thread(
                self.client.wait_for_approval,
                ticket_id=ticket_id,
                timeout=self.approval_timeout,
            )

        if not execution_auth:
            raise PolicyBlockedError(
                message=f"Action '{self.name}' has no usable execution authorization",
                action_id=eval_result.action_id,
                reason_code="MISSING_AUTHORIZATION_TOKEN",
                explanation="Gateway returned ALLOW without an execution authorization.",
            )

        # Atomically reserve this action's authorization before invoking the tool
        await asyncio.to_thread(
            self.client.claim_execution,
            action_id=eval_result.action_id,
            execution_authorization=execution_auth,
        )

        # 3. Invoke underlying tool (async or sync)
        try:
            if hasattr(self.base_tool, "ainvoke") and callable(self.base_tool.ainvoke):
                output = await self.base_tool.ainvoke(arguments)
            elif inspect.iscoroutinefunction(self.base_tool):
                output = await self.base_tool(**arguments)
            elif hasattr(self.base_tool, "invoke") and callable(self.base_tool.invoke):
                output = await asyncio.to_thread(self.base_tool.invoke, arguments)
            elif callable(self.base_tool):
                sig = inspect.signature(self.base_tool)
                if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()):
                    output = await asyncio.to_thread(self.base_tool, **arguments)
                else:
                    filtered_args = {k: v for k, v in arguments.items() if k in sig.parameters}
                    output = await asyncio.to_thread(self.base_tool, **filtered_args)
            else:
                raise TypeError(f"Base tool {type(self.base_tool)} is not callable")
        except Exception as exc:
            if execution_auth:
                try:
                    await asyncio.to_thread(
                        self.client.report_result,
                        action_id=eval_result.action_id,
                        execution_authorization=execution_auth,
                        status="failed",
                        output={"error": str(exc)},
                    )
                except Exception as report_exc:
                    raise GovernanceError(
                        f"Tool failed and governance could not record the failure: {report_exc}"
                    ) from exc
            raise

        # 4. Report outcome to tamper-evident audit ledger
        serialized = output if isinstance(output, dict) else {"result": str(output)}
        await asyncio.to_thread(
            self.client.report_result,
            action_id=eval_result.action_id,
            execution_authorization=execution_auth,
            status="succeeded",
            output=serialized,
        )

        return output

    def invoke(self, input: Any, config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        if isinstance(input, dict):
            merged = dict(input)
            merged.update(kwargs)
            return self._run(**merged)
        elif input is not None and not kwargs:
            return self._run(input)
        return self._run(**kwargs)

    async def ainvoke(self, input: Any, config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        if isinstance(input, dict):
            merged = dict(input)
            merged.update(kwargs)
            return await self._arun(**merged)
        elif input is not None and not kwargs:
            return await self._arun(input)
        return await self._arun(**kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if args and len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            return self._run(**args[0])
        elif args:
            return self._run(*args, **kwargs)
        return self._run(**kwargs)


def governed_langgraph_tool(
    client: GovernanceClient,
    tool_name: Optional[str] = None,
    operation: Optional[str] = None,
    resource: Optional[str] = None,
    auto_wait_approval: bool = False,
    approval_timeout: float = 60.0,
    handle_blocked_as_error: bool = False,
) -> Callable[[Any], GovernedLangGraphTool]:
    """Decorator converting any LangChain or Python tool into a governed LangGraph tool."""
    def decorator(base_tool: Any) -> GovernedLangGraphTool:
        return GovernedLangGraphTool(
            base_tool=base_tool,
            client=client,
            tool_name=tool_name,
            operation=operation,
            resource=resource,
            auto_wait_approval=auto_wait_approval,
            approval_timeout=approval_timeout,
            handle_blocked_as_error=handle_blocked_as_error,
        )
    return decorator


def wrap_tools(
    tools: List[Any],
    client: GovernanceClient,
    auto_wait_approval: bool = False,
    approval_timeout: float = 60.0,
) -> List[GovernedLangGraphTool]:
    """Wraps an entire list of tools to pass directly to LangGraph ToolNode."""
    return [
        GovernedLangGraphTool(
            base_tool=t,
            client=client,
            auto_wait_approval=auto_wait_approval,
            approval_timeout=approval_timeout,
        )
        for t in tools
    ]
