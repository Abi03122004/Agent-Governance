"""Generic Governed Tool Wrappers and Decorators."""

import functools
import inspect
from typing import Any, Callable, Dict, Optional

from governance_sdk.client import GovernanceClient
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRequiredError,
    PolicyBlockedError,
)
from governance_sdk.models import ActionDecision, EvaluationResult


class GovernedTool:
    """Wraps any callable with pre-execution policy evaluation and reporting."""

    def __init__(
        self,
        func: Callable[..., Any],
        client: GovernanceClient,
        tool_name: Optional[str] = None,
        operation: str = "execute",
        resource: str = "default",
        action_description: Optional[str] = None,
        auto_wait_approval: bool = False,
        approval_timeout: float = 60.0,
    ):
        self.func = func
        self.client = client
        self.tool_name = tool_name or func.__name__
        self.operation = operation
        self.resource = resource
        self.action_description = action_description or (func.__doc__ or "").strip()[:500]
        self.auto_wait_approval = auto_wait_approval
        self.approval_timeout = approval_timeout

        functools.update_wrapper(self, func)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # 1. Bind arguments into canonical dictionary
        sig = inspect.signature(self.func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)

        # 2. Derive resource if resource template or callable
        target_resource = self.resource
        if "{resource}" in target_resource or "{" in target_resource:
            try:
                target_resource = target_resource.format(**arguments)
            except Exception:
                pass

        # 3. Pre-execution gateway evaluation
        eval_result: EvaluationResult = self.client.evaluate_action(
            tool=self.tool_name,
            operation=self.operation,
            resource=target_resource,
            arguments=arguments,
            action_description=self.action_description,
        )

        # 4. Strict Decision Enforcement
        if eval_result.is_blocked:
            raise PolicyBlockedError(
                message=f"Governance policy BLOCKED execution of tool '{self.tool_name}': {eval_result.explanation}",
                action_id=eval_result.action_id,
                reason_code=eval_result.reason_code,
                explanation=eval_result.explanation,
            )

        if eval_result.is_suspended:
            raise AgentSuspendedError(
                message=f"Agent is SUSPENDED: prohibited from executing '{self.tool_name}'",
                action_id=eval_result.action_id,
                reason_code=eval_result.reason_code,
            )

        execution_auth = eval_result.execution_authorization

        if eval_result.requires_approval:
            ticket_id = eval_result.approval_ticket_id or ""
            if not self.auto_wait_approval:
                raise ApprovalRequiredError(
                    message=f"Action requires human approval (ticket: {ticket_id})",
                    action_id=eval_result.action_id,
                    ticket_id=ticket_id,
                )
            # Auto-wait for human approval
            execution_auth = self.client.wait_for_approval(
                ticket_id=ticket_id,
                timeout=self.approval_timeout,
            )

        # 5. Execute the underlying tool function
        try:
            output = self.func(*args, **kwargs)
        except Exception as exc:
            if execution_auth:
                try:
                    self.client.report_result(
                        action_id=eval_result.action_id,
                        execution_authorization=execution_auth,
                        status="failed",
                        output={"error": str(exc)},
                    )
                except Exception:
                    pass
            raise

        # 6. Report execution output to gateway audit ledger
        if execution_auth:
            try:
                serialized_output = output if isinstance(output, dict) else {"result": str(output)}
                self.client.report_result(
                    action_id=eval_result.action_id,
                    execution_authorization=execution_auth,
                    status="succeeded",
                    output=serialized_output,
                )
            except Exception:
                pass

        return output


def governed_tool(
    client: GovernanceClient,
    tool_name: Optional[str] = None,
    operation: str = "execute",
    resource: str = "default",
    action_description: Optional[str] = None,
    auto_wait_approval: bool = False,
    approval_timeout: float = 60.0,
) -> Callable[[Callable[..., Any]], GovernedTool]:
    """Decorator to wrap standard tool functions with runtime governance enforcement."""
    def decorator(fn: Callable[..., Any]) -> GovernedTool:
        return GovernedTool(
            func=fn,
            client=client,
            tool_name=tool_name,
            operation=operation,
            resource=resource,
            action_description=action_description,
            auto_wait_approval=auto_wait_approval,
            approval_timeout=approval_timeout,
        )
    return decorator

