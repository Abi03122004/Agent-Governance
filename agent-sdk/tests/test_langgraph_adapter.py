"""Unit Tests for LangGraph Governance Adapter."""

import pytest
from unittest.mock import MagicMock

from governance_sdk.adapters.langgraph import GovernedLangGraphTool, wrap_tools
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRequiredError,
    PolicyBlockedError,
)
from governance_sdk.models import ActionDecision, EvaluationResult


def create_mock_client():
    client = MagicMock()
    client.session_id = "sess_mock_123"
    client.ensure_session.return_value = "sess_mock_123"
    return client


def test_langgraph_tool_allow_flow():
    mock_client = create_mock_client()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_allow",
        decision=ActionDecision.ALLOW,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="ACTION_PERMITTED",
        explanation="Permitted",
        action_digest="sha256:digest123",
        correlation_id="req_123",
        execution_authorization="auth_token_xyz",
    )

    call_tracker = MagicMock(return_value="report content")

    def read_report(year: int):
        return call_tracker(year)

    tool = GovernedLangGraphTool(read_report, client=mock_client)
    result = tool.invoke({"year": 2024})

    assert result == "report content"
    call_tracker.assert_called_once_with(2024)
    mock_client.evaluate_action.assert_called_once()
    mock_client.report_result.assert_called_once_with(
        action_id="act_allow",
        execution_authorization="auth_token_xyz",
        status="succeeded",
        output={"result": "report content"},
    )


def test_langgraph_tool_block_flow_never_calls_function():
    mock_client = create_mock_client()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_block",
        decision=ActionDecision.BLOCK,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="DESTRUCTIVE_OPERATION",
        explanation="Destructive operations are prohibited",
        action_digest="sha256:digest_block",
        correlation_id="req_block",
    )

    destructive_func = MagicMock()

    def drop_table(table_name: str):
        destructive_func(table_name)
        return "dropped"

    tool = GovernedLangGraphTool(drop_table, client=mock_client)

    with pytest.raises(PolicyBlockedError) as exc_info:
        tool.invoke({"table_name": "production_users"})

    assert "DESTRUCTIVE_OPERATION" in exc_info.value.reason_code
    # CRITICAL INVARIANT: The underlying function was NEVER called!
    destructive_func.assert_not_called()
    mock_client.report_result.assert_not_called()


def test_langgraph_tool_suspend_flow():
    mock_client = create_mock_client()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_suspend",
        decision=ActionDecision.SUSPEND,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="AGENT_SUSPENDED",
        explanation="Agent is suspended",
        action_digest="sha256:digest_suspend",
        correlation_id="req_suspend",
    )

    func = MagicMock()
    tool = GovernedLangGraphTool(func, client=mock_client)

    with pytest.raises(AgentSuspendedError):
        tool.invoke({"arg": "val"})

    func.assert_not_called()


def test_langgraph_tool_require_approval_flow():
    mock_client = create_mock_client()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_approval",
        decision=ActionDecision.REQUIRE_APPROVAL,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="PRODUCTION_MUTATION",
        explanation="Mutation requires human approval",
        action_digest="sha256:digest_appr",
        correlation_id="req_appr",
        approval_ticket_id="appr_ticket_777",
    )

    deploy_func = MagicMock()
    tool = GovernedLangGraphTool(deploy_func, client=mock_client, auto_wait_approval=False)

    with pytest.raises(ApprovalRequiredError) as exc_info:
        tool.invoke({"env": "prod"})

    assert exc_info.value.ticket_id == "appr_ticket_777"
    deploy_func.assert_not_called()


def test_wrap_tools_utility():
    mock_client = create_mock_client()

    def tool_a(): pass
    def tool_b(): pass

    wrapped = wrap_tools([tool_a, tool_b], client=mock_client)
    assert len(wrapped) == 2
    assert all(isinstance(t, GovernedLangGraphTool) for t in wrapped)


@pytest.mark.anyio
async def test_langgraph_tool_async_ainvoke_allow():
    mock_client = create_mock_client()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_async_allow",
        decision=ActionDecision.ALLOW,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="ACTION_PERMITTED",
        explanation="Permitted",
        action_digest="sha256:digest_async",
        correlation_id="req_async_123",
        execution_authorization="auth_token_async",
    )

    async def async_fetch(url: str):
        return f"fetched:{url}"

    tool = GovernedLangGraphTool(async_fetch, client=mock_client)
    result = await tool.ainvoke({"url": "https://api.internal/data"})

    assert result == "fetched:https://api.internal/data"
    mock_client.evaluate_action.assert_called_once()
    mock_client.claim_execution.assert_called_once_with(
        action_id="act_async_allow",
        execution_authorization="auth_token_async",
    )
    mock_client.report_result.assert_called_once_with(
        action_id="act_async_allow",
        execution_authorization="auth_token_async",
        status="succeeded",
        output={"result": "fetched:https://api.internal/data"},
    )


@pytest.mark.anyio
async def test_langgraph_tool_async_ainvoke_block():
    mock_client = create_mock_client()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_async_block",
        decision=ActionDecision.BLOCK,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="PROHIBITED_ACTION",
        explanation="Not allowed",
        action_digest="sha256:digest_async_block",
        correlation_id="req_async_block",
    )

    called = False

    async def async_bad_op():
        nonlocal called
        called = True
        return "bad"

    tool = GovernedLangGraphTool(async_bad_op, client=mock_client)
    with pytest.raises(PolicyBlockedError):
        await tool.ainvoke({})

    assert not called
    mock_client.claim_execution.assert_not_called()
    mock_client.report_result.assert_not_called()


