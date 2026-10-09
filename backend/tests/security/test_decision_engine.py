"""Unit Tests for Decision Synthesis Engine and Rule #9 Deterministic Priority."""

from datetime import datetime, timedelta, timezone
import pytest

from agent_security.core.decision_engine import (
    DecisionSynthesisEngine,
    TenantMismatchError,
)
from agent_security.domain.enums import PolicyDecision, RiskLevel
from agent_security.domain.identity import AgentIdentity, AgentSession
from agent_security.domain.policy import PolicyEvaluationContext
from agent_security.domain.tool import ActionRequest, ToolDefinition


@pytest.fixture
def base_context():
    tenant_id = "tenant-prod-01"
    project_id = "proj-ops"
    now = datetime.now(timezone.utc)

    agent = AgentIdentity(
        id="agent-01",
        tenant_id=tenant_id,
        project_id=project_id,
        name="OpsAgent",
    )
    session = AgentSession(
        session_id="sess-valid-01",
        tenant_id=tenant_id,
        project_id=project_id,
        agent_id=agent.id,
        expires_at=now + timedelta(hours=1),
    )
    tool = ToolDefinition(
        name="restart_service",
        risk_level=RiskLevel.MEDIUM,
        requires_approval=False,
    )
    action = ActionRequest(
        action_id="act-restart-101",
        tenant_id=tenant_id,
        project_id=project_id,
        agent_id=agent.id,
        session_id=session.session_id,
        task_id="task-recovery",
        tool_name=tool.name,
        arguments={"service_name": "web-gateway"},
    )
    return PolicyEvaluationContext(
        action=action,
        session=session,
        agent=agent,
        tool=tool,
    )


def test_rule_9_deterministic_denial_cannot_be_overridden_by_ai(base_context):
    """Rule #9 Invariant: Deterministic BLOCK cannot be overridden even if AI risk score is 0.0."""
    base_context.ai_risk_score = 0.0
    base_context.ai_risk_reason = "AI claims 100% safe."

    decision, reason = DecisionSynthesisEngine.evaluate(base_context, PolicyDecision.BLOCK)
    assert decision == PolicyDecision.BLOCK
    assert "Deterministic policy rendered BLOCK" in reason


def test_ai_risk_score_escalates_allow_to_approval(base_context):
    """AI risk score between 0.60 and 0.85 tightens ALLOW -> REQUIRE_APPROVAL."""
    base_context.ai_risk_score = 0.72
    base_context.ai_risk_reason = "Unusual service restart sequence detected."

    decision, reason = DecisionSynthesisEngine.evaluate(base_context, PolicyDecision.ALLOW)
    assert decision == PolicyDecision.REQUIRE_APPROVAL
    assert "AI risk classifier detected elevated risk" in reason


def test_ai_risk_score_escalates_allow_to_block(base_context):
    """AI risk score >= 0.85 escalates ALLOW -> BLOCK."""
    base_context.ai_risk_score = 0.95
    base_context.ai_risk_reason = "High probability prompt injection detected."

    decision, reason = DecisionSynthesisEngine.evaluate(base_context, PolicyDecision.ALLOW)
    assert decision == PolicyDecision.BLOCK
    assert "AI risk classifier detected critical threat" in reason


def test_ai_risk_cannot_deescalate_require_approval(base_context):
    """AI risk score cannot lower REQUIRE_APPROVAL to ALLOW."""
    base_context.ai_risk_score = 0.05
    base_context.ai_risk_reason = "AI believes user is trusted."

    decision, _ = DecisionSynthesisEngine.evaluate(base_context, PolicyDecision.REQUIRE_APPROVAL)
    assert decision == PolicyDecision.REQUIRE_APPROVAL


def test_cross_tenant_access_is_blocked(base_context):
    """Threat Scenario 2: Action tenant mismatch against session raises TenantMismatchError."""
    # Modify action tenant to an unauthorized tenant
    malicious_action = base_context.action.model_copy(update={"tenant_id": "tenant-victim-corp"})
    base_context.action = malicious_action

    with pytest.raises(TenantMismatchError):
        DecisionSynthesisEngine.evaluate(base_context, PolicyDecision.ALLOW)


def test_suspended_agent_renders_suspend(base_context):
    """Kill Switch Invariant: A suspended agent identity always renders SUSPEND."""
    base_context.agent.is_suspended = True
    decision, reason = DecisionSynthesisEngine.evaluate(base_context, PolicyDecision.ALLOW)
    assert decision == PolicyDecision.SUSPEND
    assert "SUSPENDED" in reason
