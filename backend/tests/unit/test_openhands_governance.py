"""Unit tests for OpenHands Runtime Governance Mediation with Mocked Gateway."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

openhands_dir = Path(__file__).resolve().parents[3] / "external" / "OpenHands"
if str(openhands_dir) not in sys.path:
    sys.path.insert(0, str(openhands_dir))

from openhands.events.action.commands import CmdRunAction
from openhands.events.action.files import FileReadAction, FileWriteAction
from openhands.events.observation.commands import CmdOutputObservation
from openhands.events.observation.error import ErrorObservation
from openhands.runtime.governance_client import GovernanceClient, MediationDecision


class DummyRuntime:
    """Mock Runtime imitating OpenHands base.py."""

    def __init__(self, governance_client: GovernanceClient):
        self._governance_client = governance_client
        self.closed = False
        self.executed_tools = []

    def close(self):
        self.closed = True

    def run(self, action: CmdRunAction):
        self.executed_tools.append(action.command)
        return CmdOutputObservation(content="total 0\nfile.txt", command=action.command, exit_code=0)

    def read(self, action: FileReadAction):
        self.executed_tools.append(action.path)
        return CmdOutputObservation(content="secret_value", command="", exit_code=0)

    def write(self, action: FileWriteAction):
        self.executed_tools.append(action.path)
        return CmdOutputObservation(content="ok", command="", exit_code=0)

    def run_action(self, action):
        action_type = getattr(action, "action", "")
        gov_client = self._governance_client

        if gov_client and gov_client.is_configured and gov_client.is_governed_action(action):
            decision = gov_client.mediate(action)
            if decision.decision == "BLOCK":
                return ErrorObservation(
                    content=f"Governance Policy Blocked Action [{decision.reason_code}]: {decision.explanation}",
                    error_id=decision.reason_code,
                )
            elif decision.decision == "SUSPEND":
                self.close()
                return ErrorObservation(
                    content=f"Governance Security TRIPWIRE: Agent SUSPENDED. Action halted: {decision.explanation}",
                    error_id="AGENT_SUSPENDED",
                )
            elif decision.decision == "ALLOW":
                obs = None
                exec_status = "succeeded"
                try:
                    obs = getattr(self, action_type)(action)
                    if isinstance(obs, ErrorObservation):
                        exec_status = "failed"
                    return obs
                except Exception as exc:
                    exec_status = "failed"
                    obs = ErrorObservation(f"Tool execution failed: {str(exc)}")
                    return obs
                finally:
                    if decision.action_id and decision.execution_authorization:
                        gov_client.report_result(
                            action_id=decision.action_id,
                            execution_authorization=decision.execution_authorization,
                            status=exec_status,
                            output={"observation": getattr(obs, "content", "")[:2048]},
                        )

        return getattr(self, action_type)(action)


def test_action_mapping():
    client = GovernanceClient(gateway_url="http://mock-gw:8000", api_key="secret-key")
    cmd_act = CmdRunAction(command="ls -la")
    mapped_cmd = client.map_action(cmd_act)
    assert mapped_cmd["tool"] == "shell"
    assert mapped_cmd["operation"] == "execute"
    assert mapped_cmd["resource"] == "ls -la"

    file_act = FileReadAction(path="/etc/passwd")
    mapped_file = client.map_action(file_act)
    assert mapped_file["tool"] == "filesystem"
    assert mapped_file["operation"] == "read"
    assert mapped_file["resource"] == "/etc/passwd"


def test_decision_allow_executes_and_reports_result():
    client = GovernanceClient(gateway_url="http://mock-gw:8000", api_key="secret-key")
    runtime = DummyRuntime(client)

    with patch.object(client, "_request_with_retry") as mock_req:
        # Session response
        session_resp = MagicMock(status_code=201)
        session_resp.json.return_value = {"session_id": "sess_123"}

        # Evaluate response: ALLOW
        eval_resp = MagicMock(status_code=200)
        eval_resp.json.return_value = {
            "decision": "ALLOW",
            "action_id": "act_allow_1",
            "execution_authorization": "token_auth_valid_1234567890",
            "reason_code": "PERMITTED",
            "explanation": "Allowed shell execution",
        }

        # Execute broker response: 200
        exec_resp = MagicMock(status_code=200)
        exec_resp.json.return_value = {"status": "EXECUTED"}

        # Report result response
        result_resp = MagicMock(status_code=200)

        mock_req.side_effect = [session_resp, eval_resp, exec_resp, result_resp]

        action = CmdRunAction(command="ls -la")
        obs = runtime.run_action(action)

        assert not isinstance(obs, ErrorObservation)
        assert "total 0" in obs.content
        assert "ls -la" in runtime.executed_tools
        assert mock_req.call_count == 4


def test_decision_block_never_executes_tool():
    client = GovernanceClient(gateway_url="http://mock-gw:8000", api_key="secret-key")
    runtime = DummyRuntime(client)

    with patch.object(client, "_request_with_retry") as mock_req:
        session_resp = MagicMock(status_code=201)
        session_resp.json.return_value = {"session_id": "sess_123"}

        eval_resp = MagicMock(status_code=200)
        eval_resp.json.return_value = {
            "decision": "BLOCK",
            "action_id": "act_block_1",
            "reason_code": "RESOURCE_NOT_PERMITTED",
            "explanation": "Access to .env is forbidden",
        }

        mock_req.side_effect = [session_resp, eval_resp]

        action = FileReadAction(path=".env")
        obs = runtime.run_action(action)

        assert isinstance(obs, ErrorObservation)
        assert "RESOURCE_NOT_PERMITTED" in obs.content
        assert ".env" not in runtime.executed_tools


def test_decision_require_approval_polls_and_executes():
    client = GovernanceClient(
        gateway_url="http://mock-gw:8000",
        api_key="secret-key",
        poll_interval=0.01,
        poll_timeout=1.0,
    )
    runtime = DummyRuntime(client)

    with patch.object(client, "_request_with_retry") as mock_req:
        session_resp = MagicMock(status_code=201)
        session_resp.json.return_value = {"session_id": "sess_123"}

        eval_resp = MagicMock(status_code=200)
        eval_resp.json.return_value = {
            "decision": "REQUIRE_APPROVAL",
            "action_id": "act_appr_1",
            "approval_ticket_id": "ticket_abc_123",
            "reason_code": "PRODUCTION_MUTATION",
            "explanation": "Requires approval",
        }

        # Polling: first PENDING, second APPROVED
        poll_pending = MagicMock(status_code=200)
        poll_pending.json.return_value = {"status": "PENDING"}

        poll_approved = MagicMock(status_code=200)
        poll_approved.json.return_value = {
            "status": "APPROVED",
            "execution_authorization": "token_approved_from_polling_999",
        }

        exec_resp = MagicMock(status_code=200)
        exec_resp.json.return_value = {"status": "EXECUTED"}

        result_resp = MagicMock(status_code=200)

        mock_req.side_effect = [session_resp, eval_resp, poll_pending, poll_approved, exec_resp, result_resp]

        action = FileWriteAction(path="schema.sql", content="ALTER TABLE accounts")
        obs = runtime.run_action(action)

        assert not isinstance(obs, ErrorObservation)
        assert "schema.sql" in runtime.executed_tools


def test_decision_suspend_halts_and_closes_runtime():
    client = GovernanceClient(gateway_url="http://mock-gw:8000", api_key="secret-key")
    runtime = DummyRuntime(client)

    with patch.object(client, "_request_with_retry") as mock_req:
        session_resp = MagicMock(status_code=201)
        session_resp.json.return_value = {"session_id": "sess_123"}

        eval_resp = MagicMock(status_code=200)
        eval_resp.json.return_value = {
            "decision": "SUSPEND",
            "action_id": "act_suspend_1",
            "reason_code": "TRIPWIRE_TRIGGERED",
            "explanation": "Critical security tripwire triggered",
        }

        mock_req.side_effect = [session_resp, eval_resp]

        action = CmdRunAction(command="rm -rf /")
        obs = runtime.run_action(action)

        assert isinstance(obs, ErrorObservation)
        assert "SUSPENDED" in obs.content
        assert runtime.closed is True
        assert "rm -rf /" not in runtime.executed_tools


def test_fail_closed_when_gateway_down():
    client = GovernanceClient(gateway_url="http://mock-gw:8000", api_key="secret-key")
    runtime = DummyRuntime(client)

    with patch.object(client, "_request_with_retry", return_value=None):
        action = CmdRunAction(command="ls")
        obs = runtime.run_action(action)

        assert isinstance(obs, ErrorObservation)
        assert "fail-closed" in obs.content.lower()
        assert len(runtime.executed_tools) == 0


def test_expired_or_invalid_token_rejected_at_broker():
    client = GovernanceClient(gateway_url="http://mock-gw:8000", api_key="secret-key")
    runtime = DummyRuntime(client)

    with patch.object(client, "_request_with_retry") as mock_req:
        session_resp = MagicMock(status_code=201)
        session_resp.json.return_value = {"session_id": "sess_123"}

        eval_resp = MagicMock(status_code=200)
        eval_resp.json.return_value = {
            "decision": "ALLOW",
            "action_id": "act_expired",
            "execution_authorization": "token_expired_12345",
        }

        # Broker returns 403 Expired
        exec_resp = MagicMock(status_code=403)
        exec_resp.json.return_value = {"detail": "Invalid, expired, or already-used execution authorization"}

        mock_req.side_effect = [session_resp, eval_resp, exec_resp]

        action = CmdRunAction(command="cat data.txt")
        obs = runtime.run_action(action)

        assert isinstance(obs, ErrorObservation)
        assert "rejected" in obs.content.lower()
        assert "cat data.txt" not in runtime.executed_tools
