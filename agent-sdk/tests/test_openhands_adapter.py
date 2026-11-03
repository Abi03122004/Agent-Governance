"""Unit tests for OpenHands Governance Adapter."""

from unittest.mock import MagicMock, patch
import pytest

from governance_sdk.adapters.openhands import (
    OpenHandsGovernanceAdapter,
    infer_openhands_action_semantics,
)
from governance_sdk.exceptions import (
    AgentSuspendedError,
    GatewayConnectionError,
    PolicyBlockedError,
)
from governance_sdk.models import ActionDecision, EvaluationResult, ExecutionResult


class FakeCmdRunAction:
    def __init__(self, command: str, thought: str = "running command"):
        self.action = "run"
        self.command = command
        self.thought = thought
        self.is_static = False


class FakeFileReadAction:
    def __init__(self, path: str):
        self.action = "read"
        self.path = path
        self.view_range = [1, 50]
        self.thought = "reading file"


class FakeFileWriteAction:
    def __init__(self, path: str, content: str):
        self.action = "write"
        self.path = path
        self.content = content
        self.thought = "writing file"


class FakeErrorObservation:
    def __init__(self, content: str, error_id: str = "ERROR"):
        self.content = content
        self.error_id = error_id


def test_infer_openhands_action_semantics():
    cmd = FakeCmdRunAction("cat /etc/hosts")
    tool, op, res, args = infer_openhands_action_semantics(cmd)
    assert tool == "shell"
    assert op == "read"
    assert res == "cat /etc/hosts"
    assert args["command"] == "cat /etc/hosts"

    destructive_cmd = FakeCmdRunAction("rm -rf /var/data")
    tool, op, res, args = infer_openhands_action_semantics(destructive_cmd)
    assert tool == "shell"
    assert op == "delete"

    read_act = FakeFileReadAction("/var/log/syslog")
    tool, op, res, args = infer_openhands_action_semantics(read_act)
    assert tool == "filesystem"
    assert op == "read"
    assert res == "/var/log/syslog"

    write_act = FakeFileWriteAction("/tmp/test.txt", "hello world")
    tool, op, res, args = infer_openhands_action_semantics(write_act)
    assert tool == "filesystem"
    assert op == "write"
    assert res == "/tmp/test.txt"
    assert args["content_length"] == 11


def test_openhands_allow_flow():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_allow_123",
        decision=ActionDecision.ALLOW,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="DEFAULT_ALLOW",
        explanation="Allowed",
        action_digest="sha256:digest123",
        correlation_id="corr_123",
        execution_authorization="token_auth_xyz",
    )
    mock_client.execute_action.return_value = ExecutionResult(
        action_id="act_allow_123",
        status="EXECUTED",
        result={"message": "ok"},
    )

    adapter = OpenHandsGovernanceAdapter(client=mock_client)
    execute_called = False

    def fake_execute(action):
        nonlocal execute_called
        execute_called = True
        return {"observation": "success", "content": "file contents"}

    action = FakeFileReadAction("/workspace/src/app.py")
    obs = adapter.mediate_and_execute(action, fake_execute)

    assert execute_called is True
    assert obs["content"] == "file contents"
    mock_client.evaluate_action.assert_called_once()
    mock_client.report_result.assert_called_once()


def test_openhands_block_flow_never_calls_tool():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_block_123",
        decision=ActionDecision.BLOCK,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="SECURITY_VIOLATION",
        explanation="Access to sensitive file blocked by governance policy",
        action_digest="sha256:digest_block",
        correlation_id="corr_block",
    )

    adapter = OpenHandsGovernanceAdapter(client=mock_client)
    tool_called = False

    def fake_execute(action):
        nonlocal tool_called
        tool_called = True
        return {"observation": "should_not_happen"}

    action = FakeFileReadAction("/etc/shadow")
    obs = adapter.mediate_and_execute(
        action,
        fake_execute,
        observation_factory=lambda c, e: FakeErrorObservation(c, e),
    )

    assert tool_called is False
    assert isinstance(obs, FakeErrorObservation)
    assert "Governance Policy Blocked Action [SECURITY_VIOLATION]" in obs.content
    assert obs.error_id == "SECURITY_VIOLATION"
    mock_client.execute_action.assert_not_called()


def test_openhands_suspend_flow():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_susp_123",
        decision=ActionDecision.SUSPEND,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="AGENT_SUSPENDED",
        explanation="Agent tripwire triggered",
        action_digest="sha256:digest_susp",
        correlation_id="corr_susp",
    )

    adapter = OpenHandsGovernanceAdapter(client=mock_client)
    action = FakeCmdRunAction("whoami")
    obs = adapter.mediate_and_execute(
        action,
        lambda a: {"observation": "ok"},
        observation_factory=lambda c, e: FakeErrorObservation(c, e),
    )

    assert adapter.is_suspended is True
    assert "Governance Security TRIPWIRE: Agent SUSPENDED" in obs.content

    # Subsequent actions should be blocked locally without calling evaluate
    mock_client.evaluate_action.reset_mock()
    obs2 = adapter.mediate_and_execute(
        action,
        lambda a: {"observation": "ok"},
        observation_factory=lambda c, e: FakeErrorObservation(c, e),
    )
    mock_client.evaluate_action.assert_not_called()
    assert "Agent SUSPENDED" in obs2.content


def test_openhands_require_approval_flow():
    mock_client = MagicMock()
    mock_client.evaluate_action.return_value = EvaluationResult(
        action_id="act_appr_123",
        decision=ActionDecision.REQUIRE_APPROVAL,
        policy_id="runtime-default-v1",
        policy_version=1,
        reason_code="PRODUCTION_WRITE",
        explanation="Production mutation requires operator review",
        action_digest="sha256:digest_appr",
        correlation_id="corr_appr",
        approval_ticket_id="ticket_999",
    )
    mock_client.wait_for_approval.return_value = "token_after_approval"
    mock_client.execute_action.return_value = ExecutionResult(
        action_id="act_appr_123",
        status="EXECUTED",
        result={"message": "ok"},
    )

    adapter = OpenHandsGovernanceAdapter(client=mock_client, auto_wait_approval=True)
    tool_executed = False

    def fake_execute(action):
        nonlocal tool_executed
        tool_executed = True
        return {"observation": "written"}

    action = FakeFileWriteAction("/app/prod_config.json", '{"env":"prod"}')
    obs = adapter.mediate_and_execute(action, fake_execute)

    assert tool_executed is True
    mock_client.wait_for_approval.assert_called_once_with(
        ticket_id="ticket_999",
        timeout=60.0,
        poll_interval=1.5,
    )
    mock_client.report_result.assert_called_once()


def test_openhands_fail_closed_on_gateway_error():
    mock_client = MagicMock()
    mock_client.evaluate_action.side_effect = GatewayConnectionError("Connection refused: 8000")

    adapter = OpenHandsGovernanceAdapter(client=mock_client, fail_closed=True)
    tool_called = False

    def fake_execute(action):
        nonlocal tool_called
        tool_called = True
        return {"observation": "should_fail"}

    action = FakeCmdRunAction("echo test")
    obs = adapter.mediate_and_execute(
        action,
        fake_execute,
        observation_factory=lambda c, e: FakeErrorObservation(c, e),
    )

    assert tool_called is False
    assert "Governance Gateway Unavailable (fail-closed)" in obs.content
    assert obs.error_id == "GATEWAY_UNAVAILABLE"
