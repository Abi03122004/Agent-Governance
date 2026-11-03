"""Unit Tests for Governance SDK Client, Models, and Exceptions."""

import pytest
from unittest.mock import MagicMock, patch
import httpx

from governance_sdk.authentication import AgentAuthenticator
from governance_sdk.client import GovernanceClient
from governance_sdk.exceptions import (
    AgentSuspendedError,
    ApprovalRequiredError,
    AuthenticationError,
    PolicyBlockedError,
    TenantIsolationError,
)
from governance_sdk.models import ActionDecision, EvaluationResult


def test_authenticator_headers():
    auth = AgentAuthenticator("agt_test_token_123456789")
    headers = auth.get_auth_headers()
    assert headers["Authorization"] == "Bearer agt_test_token_123456789"
    assert "AgentGovernance-SDK" in headers["User-Agent"]
    assert auth.masked_token == "agt_...6789"


def test_evaluation_result_properties():
    res_allow = EvaluationResult(
        action_id="act_1",
        decision=ActionDecision.ALLOW,
        policy_id="pol_1",
        policy_version=1,
        reason_code="OK",
        explanation="Permitted",
        action_digest="sha256:abc",
        correlation_id="req_1",
        execution_authorization="token_abc",
    )
    assert res_allow.is_allowed is True
    assert res_allow.is_blocked is False

    res_block = EvaluationResult(
        action_id="act_2",
        decision=ActionDecision.BLOCK,
        policy_id="pol_1",
        policy_version=1,
        reason_code="BLOCKED",
        explanation="Prohibited",
        action_digest="sha256:xyz",
        correlation_id="req_2",
    )
    assert res_block.is_blocked is True
    assert res_block.is_allowed is False


def test_client_authentication_failure():
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"detail": "Invalid agent credentials"}
        mock_post.return_value = mock_resp

        client = GovernanceClient(agent_token="agt_invalid", auto_start_session=False)
        with pytest.raises(AuthenticationError):
            client.start_session()


def test_client_suspension_detection():
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"detail": "Agent is suspended"}
        mock_post.return_value = mock_resp

        client = GovernanceClient(agent_token="agt_suspended", auto_start_session=False)
        with pytest.raises(AgentSuspendedError):
            client.start_session()

