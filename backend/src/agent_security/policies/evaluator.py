"""Decision Synthesis Engine Enforcing Deterministic Priority and Safety Rules."""

from typing import Optional, Tuple
from agent_security.domain.enums import PolicyDecision
from agent_security.domain.policy import PolicyEvaluationContext


class OrganizationMismatchError(ValueError):
    """Raised when an action request attempts cross-organization access."""
    pass


TenantMismatchError = OrganizationMismatchError


class DecisionSynthesisEngine:
    """Combines deterministic evaluation and secondary AI risk advisories.
    
    Guarantees:
    1. Deterministic DENY/BLOCK/SUSPEND can never be overridden by AI risk scores.
    2. AI risk scores can only tighten/escalate decisions (One-Way Escalation).
    3. Session and Organization integrity are validated before policy evaluation.
    """

    AI_ESCALATE_TO_APPROVAL_THRESHOLD: float = 0.60
    AI_ESCALATE_TO_BLOCK_THRESHOLD: float = 0.85

    @classmethod
    def evaluate(
        cls,
        context: PolicyEvaluationContext,
        deterministic_verdict: PolicyDecision,
    ) -> Tuple[PolicyDecision, str]:
        """Synthesize the final platform decision."""
        action_org = context.action.tenant_id or context.action.organization_id
        session_org = context.session.tenant_id or context.session.organization_id
        agent_org = context.agent.tenant_id or context.agent.organization_id
        if action_org != session_org:
            raise OrganizationMismatchError(
                f"Cross-organization violation: Action organization '{action_org}' "
                f"does not match session organization '{session_org}'."
            )
        if agent_org != session_org:
            raise OrganizationMismatchError(
                f"Identity organization '{agent_org}' does not match session organization '{session_org}'."
            )

        if context.agent.is_suspended:
            return (
                PolicyDecision.SUSPEND,
                "Agent identity is marked as SUSPENDED by administrator or kill switch.",
            )

        if not context.session.is_valid:
            return (
                PolicyDecision.BLOCK,
                "Agent session is expired or revoked.",
            )

        # Invariant 4: Rule 9 Enforcement
        if deterministic_verdict in (PolicyDecision.BLOCK, PolicyDecision.SUSPEND):
            return (
                deterministic_verdict,
                f"Deterministic policy rendered {deterministic_verdict.value}. Rule 9 invariant prohibits override.",
            )

        # One-way escalation based on AI risk score
        ai_score = context.ai_risk_score if context.ai_risk_score is not None else 0.0

        if ai_score >= cls.AI_ESCALATE_TO_BLOCK_THRESHOLD:
            return (
                PolicyDecision.BLOCK,
                f"AI risk classifier detected critical threat ({ai_score:.2f}). Escalate to BLOCK.",
            )

        if ai_score >= cls.AI_ESCALATE_TO_APPROVAL_THRESHOLD:
            if deterministic_verdict == PolicyDecision.ALLOW:
                return (
                    PolicyDecision.REQUIRE_APPROVAL,
                    f"AI risk classifier detected elevated risk ({ai_score:.2f}). Escalate to REQUIRE_APPROVAL.",
                )

        return (
            deterministic_verdict,
            f"Evaluated successfully under deterministic policy ({deterministic_verdict.value}).",
        )
