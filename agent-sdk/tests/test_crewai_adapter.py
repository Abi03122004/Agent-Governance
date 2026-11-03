"""Unit tests for CrewAI Governance Adapter."""

from unittest.mock import MagicMock, patch
from typing import Any, Optional
import pytest

from governance_sdk.adapters.crewai import (
    CrewAIGovernanceHook,
    GovernedCrewAITool,
    infer_crewai_action_semantics,
)
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRejectedError,
    ApprovalTimeoutError,
    AuthenticationError,
    GatewayConnectionError,
    PolicyBlockedError,
)
from governance_sdk.models import ActionDecision, EvaluationResult


def make_eval_result(
    action_id: str,
    decision: ActionDecision,
    execution_authorization: Optional[str] = None,
    approval_ticket_id: Optional[str] = None,
    reason_code: str = "POLICY_EVAL",
    explanation: str = "Evaluation explanation",
    risk_score: int = 10,
) -> EvaluationResult:
    return EvaluationResult(
        action_id=action_id,
        decision=decision,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code=reason_code,
        explanation=explanation,
        action_digest="sha256:digest123",
        correlation_id="corr_123",
        risk_score=risk_score,
        execution_authorization=execution_authorization,
        approval_ticket_id=approval_ticket_id,
    )


class FakeHookContext:
    """Mock CrewAI ToolCallHookContext for testing."""

    def __init__(
        self,
        tool_name: str,
        tool_input: dict,
        tool: Any = None,
        agent: Any = None,
        task: Any = None,
        crew: Any = None,
        tool_result: Optional[str] = None,
        raw_tool_result: Any = None,
    ):
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.tool = tool
        self.agent = agent
        self.task = task
        self.crew = crew
        self.tool_result = tool_result
        self.raw_tool_result = raw_tool_result


class FakeAgent:
    def __init__(self, role: str = "DevOps Engineer"):
        self.role = role


def test_infer_crewai_action_semantics():
    # 1. Shell commands
    tool, op, res, args = infer_crewai_action_semantics("bash", {"command": "rm -rf /var/log"})
    assert tool == "shell"
    assert op == "delete"
    assert res == "rm -rf /var/log"

    tool, op, res, args = infer_crewai_action_semantics("terminal", {"command": "cat config.yaml"})
    assert tool == "shell"
    assert op == "read"
    assert res == "config.yaml" or res == "cat config.yaml"

    # 2. File tools
    tool, op, res, args = infer_crewai_action_semantics("delete_file", {"path": "/tmp/test.txt"})
    assert tool == "filesystem"
    assert op == "delete"
    assert res == "/tmp/test.txt"

    tool, op, res, args = infer_crewai_action_semantics("write_file", {"file_path": "/var/app/index.js", "data": "console.log()"})
    assert tool == "filesystem"
    assert op == "write"
    assert res == "/var/app/index.js"

    # 3. HTTP tools
    tool, op, res, args = infer_crewai_action_semantics("browse_web", {"url": "https://api.github.com"})
    assert tool == "http"
    assert op == "read"
    assert res == "https://api.github.com"

    # 4. Custom tool
    tool, op, res, args = infer_crewai_action_semantics("calculator", {"expression": "2+2"})
    assert tool == "calculator"
    assert op == "execute"


def test_crewai_hook_allow_flow():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = make_eval_result(
        action_id="act_allow_123",
        decision=ActionDecision.ALLOW,
        execution_authorization="token_auth_xyz",
        risk_score=10,
        reason_code="POLICY_ALLOW",
        explanation="Permitted operation",
    )

    hook = CrewAIGovernanceHook(client=mock_client)
    ctx = FakeHookContext(tool_name="read_file", tool_input={"path": "/docs/readme.md"})

    # Before hook allows (returns None)
    res = hook.before_tool_call(ctx)
    assert res is None
    assert id(ctx) in hook._pending_actions

    # After hook logs result
    ctx.tool_result = "File content here"
    ctx.raw_tool_result = "File content here"
    hook.after_tool_call(ctx)

    mock_client.report_result.assert_called_once_with(
        action_id="act_allow_123",
        execution_authorization="token_auth_xyz",
        status="succeeded",
        output={"result": "File content here"},
    )
    assert id(ctx) not in hook._pending_actions


def test_crewai_hook_block_flow():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = make_eval_result(
        action_id="act_block_456",
        decision=ActionDecision.BLOCK,
        risk_score=95,
        reason_code="BLOCKED_DESTRUCTIVE_COMMAND",
        explanation="Deletion of critical files is prohibited",
    )

    hook = CrewAIGovernanceHook(client=mock_client)
    ctx = FakeHookContext(tool_name="delete_file", tool_input={"path": "/production/db.sqlite"})

    # Before hook returns False to abort tool execution
    res = hook.before_tool_call(ctx)
    assert res is False
    assert hook.last_blocked_reason == "BLOCKED_DESTRUCTIVE_COMMAND"
    assert id(ctx) not in hook._pending_actions


def test_crewai_hook_approval_flow_approved():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = make_eval_result(
        action_id="act_approval_789",
        decision=ActionDecision.REQUIRE_APPROVAL,
        approval_ticket_id="ticket_001",
        risk_score=75,
        reason_code="REQUIRE_HUMAN_APPROVAL",
        explanation="Requires human approval",
    )
    mock_client.wait_for_approval.return_value = "approved_auth_token_999"

    hook = CrewAIGovernanceHook(client=mock_client, auto_wait_approval=True)
    ctx = FakeHookContext(tool_name="deploy_service", tool_input={"target": "prod-cluster"})

    res = hook.before_tool_call(ctx)
    assert res is None  # Permitted following human approval
    assert hook._pending_actions[id(ctx)] == ("act_approval_789", "approved_auth_token_999")
    mock_client.wait_for_approval.assert_called_once_with(ticket_id="ticket_001", timeout=60.0, poll_interval=1.0)


def test_crewai_hook_approval_flow_rejected():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = make_eval_result(
        action_id="act_approval_fail",
        decision=ActionDecision.REQUIRE_APPROVAL,
        approval_ticket_id="ticket_002",
        risk_score=80,
    )
    mock_client.wait_for_approval.side_effect = ApprovalRejectedError("ticket_002")

    hook = CrewAIGovernanceHook(client=mock_client, auto_wait_approval=True)
    ctx = FakeHookContext(tool_name="restart_service", tool_input={"target": "billing"})

    res = hook.before_tool_call(ctx)
    assert res is False
    assert "APPROVAL_REJECTED" in (hook.last_blocked_reason or "")


def test_crewai_hook_suspension_tripwire():
    mock_client = MagicMock()
    mock_client.evaluate_action.side_effect = AgentSuspendedError("Agent suspended for policy violations.")

    hook = CrewAIGovernanceHook(client=mock_client)
    ctx1 = FakeHookContext(tool_name="read_file", tool_input={"path": "/data/secrets.env"})

    res1 = hook.before_tool_call(ctx1)
    assert res1 is False
    assert hook.is_suspended is True

    # Subsequent tool call is tripped immediately without invoking gateway
    mock_client.evaluate_action.reset_mock()
    ctx2 = FakeHookContext(tool_name="read_file", tool_input={"path": "/data/other.txt"})
    res2 = hook.before_tool_call(ctx2)
    assert res2 is False
    assert mock_client.evaluate_action.call_count == 0


def test_crewai_hook_target_filtering():
    mock_client = MagicMock()
    managed_agent = FakeAgent(role="Managed Agent")
    unmanaged_agent = FakeAgent(role="Unmanaged Agent")

    hook = CrewAIGovernanceHook(client=mock_client, target_agent=managed_agent)

    # Tool call from unmanaged agent must pass through with None and no gateway evaluation
    unmanaged_ctx = FakeHookContext(tool_name="tool_x", tool_input={"x": 1}, agent=unmanaged_agent)
    assert hook.before_tool_call(unmanaged_ctx) is None
    assert mock_client.evaluate_action.call_count == 0


def test_crewai_hook_fail_closed():
    mock_client = MagicMock()
    mock_client.evaluate_action.side_effect = GatewayConnectionError("Connection refused")

    hook = CrewAIGovernanceHook(client=mock_client, fail_closed=True)
    ctx = FakeHookContext(tool_name="tool_x", tool_input={"x": 1})

    res = hook.before_tool_call(ctx)
    assert res is False
    assert "GATEWAY_UNAVAILABLE" in (hook.last_blocked_reason or "")


def test_governed_crewai_tool_wrapper():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = make_eval_result(
        action_id="act_tool_1",
        decision=ActionDecision.ALLOW,
        execution_authorization="token_123",
    )

    def inner_fn(val: str) -> str:
        return f"result: {val}"

    wrapper = GovernedCrewAITool(base_tool=inner_fn, client=mock_client, tool_name="my_inner_tool")
    res = wrapper.run(val="hello")
    assert res == "result: hello"
    mock_client.report_result.assert_called_once()
