"""Unit Tests for Domain Contracts, Schemas, and Enums."""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from agent_security.domain.enums import (
    ApprovalStatus,
    AuditSeverity,
    ExecutionState,
    PolicyDecision,
    RiskLevel,
)
from agent_security.domain.identity import (
    AgentIdentity,
    AgentSession,
    Project,
    Tenant,
)
from agent_security.domain.tool import (
    ActionRequest,
    ToolDefinition,
)


def test_core_policy_decision_values():
    """Verify that PolicyDecision contains exactly the 4 required governance decisions."""
    expected = {"ALLOW", "BLOCK", "REQUIRE_APPROVAL", "SUSPEND"}
    actual = {decision.value for decision in PolicyDecision}
    assert actual == expected


def test_tenant_and_project_creation():
    tenant = Tenant(id="tenant-alpha", name="Alpha Corp")
    project = Project(id="proj-finance", tenant_id=tenant.id, name="Financial Agents")
    
    assert tenant.id == "tenant-alpha"
    assert project.tenant_id == "tenant-alpha"
    assert tenant.is_active is True


def test_invalid_tenant_id_raises_validation_error():
    with pytest.raises(ValidationError):
        Tenant(id="INVALID_CAPS_WITH_SPACES", name="Bad")


def test_agent_session_validity():
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)
    past = now - timedelta(minutes=5)

    valid_session = AgentSession(
        session_id="sess-12345678",
        tenant_id="tenant-alpha",
        project_id="proj-123",
        agent_id="agent-007",
        expires_at=future,
    )
    assert valid_session.is_valid(now) is True

    # Expired session
    expired_session = AgentSession(
        session_id="sess-expired-12",
        tenant_id="tenant-alpha",
        project_id="proj-123",
        agent_id="agent-007",
        expires_at=past,
    )
    assert expired_session.is_valid(now) is False

    # Revoked session
    revoked_session = AgentSession(
        session_id="sess-revoked-12",
        tenant_id="tenant-alpha",
        project_id="proj-123",
        agent_id="agent-007",
        expires_at=future,
        is_revoked=True,
    )
    assert revoked_session.is_valid(now) is False


def test_action_request_creation():
    action = ActionRequest(
        action_id="act-987654321",
        tenant_id="tenant-alpha",
        project_id="proj-finance",
        agent_id="agent-007",
        session_id="sess-12345678",
        task_id="task-summary-1",
        tool_name="transfer_funds",
        arguments={"amount": 500, "currency": "USD"},
    )
    assert action.tool_name == "transfer_funds"
    assert action.arguments["amount"] == 500
