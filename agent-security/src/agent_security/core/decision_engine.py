"""Decision Synthesis Engine Enforcing Deterministic Priority and Safety Rules."""

from typing import Optional, Tuple
from agent_security.domain.enums import PolicyDecision
from agent_security.domain.policy import PolicyEvaluationContext


class TenantMismatchError(ValueError):
    """Raised when an action request attempts cross-tenant access."""
    pass


class DecisionSynthesisEngine:
    """Combines deterministic evaluation and secondary AI risk advisories.
    
    Guarantees:
    1. Deterministic DENY/BLOCK/SUSPEND can never be overridden by AI risk scores.
    2. AI risk scores can only tighten/escalate decisions (One-Way Escalation).
    3. Session and Tenant integrity are validated before policy evaluation.
    """

    AI_ESCALATE_TO_APPROVAL_THRESHOLD: float = 0.60
    AI_ESCALATE_TO_BLOCK_THRESHOLD: float = 0.85

    @classmethod
    def evaluate(
        cls,
        context: PolicyEvaluationContext,
        deterministic_verdict: PolicyDecision,
    ) -> Tuple[PolicyDecision, str]:
        """Synthesize the final platform decision.
        
        Returns:
            Tuple[PolicyDecision, str]: (Final Decision, Justification Reason)
        """
        # 1. Tenant Sandboxing Invariant (Threat Scenario 2)
        if context.action.tenant_id != context.session.tenant_id:
            raise TenantMismatchError(
                f"Cross-tenant violation: Action tenant '{context.action.tenant_id}' "
                f"does not match session tenant '{context.session.tenant_id}'."
            )
        if context.agent.tenant_id != context.session.tenant_id:
            raise TenantMismatchError(
                f"Identity tenant '{context.agent.tenant_id}' does not match session tenant '{context.session.tenant_id}'."
            )

        # 2. Agent Suspension Check (Kill switch)
        if context.agent.is_suspended:
            return (
                PolicyDecision.SUSPEND,
                "Agent identity is marked as SUSPENDED by administrator or kill switch.",
            )

        # 3. Session Revocation / Expiry Check
        if not context.session.is_valid():
            return (
                PolicyDecision.BLOCK,
                "Agent session is expired or has been revoked.",
            )

        # 4. Inherent Tool Approval Requirement
        baseline_verdict = deterministic_verdict
        if baseline_verdict == PolicyDecision.ALLOW and context.tool.requires_approval:
            baseline_verdict = PolicyDecision.REQUIRE_APPROVAL

        # 5. Rule #9 Invariant: Deterministic denials are FINAL
        if baseline_verdict in (PolicyDecision.BLOCK, PolicyDecision.SUSPEND):
            return (
                baseline_verdict,
                f"Deterministic policy rendered {baseline_verdict.value}. Final verdict cannot be overridden.",
            )

        # 6. Secondary AI Risk Score Evaluation (One-way escalation only)
        ai_score = context.ai_risk_score
        if ai_score is not None:
            if ai_score >= cls.AI_ESCALATE_TO_BLOCK_THRESHOLD:
                return (
                    PolicyDecision.BLOCK,
                    f"AI risk classifier detected critical threat (score={ai_score:.2f}). "
                    f"Decision escalated to BLOCK. Reason: {context.ai_risk_reason or 'Critical anomaly'}",
                )
            elif ai_score >= cls.AI_ESCALATE_TO_APPROVAL_THRESHOLD:
                if baseline_verdict == PolicyDecision.ALLOW:
                    return (
                        PolicyDecision.REQUIRE_APPROVAL,
                        f"AI risk classifier detected elevated risk (score={ai_score:.2f}). "
                        f"Decision tightened from ALLOW to REQUIRE_APPROVAL. Reason: {context.ai_risk_reason or 'Elevated risk'}",
                    )

        # Baseline decision stands
        return (baseline_verdict, f"Deterministic evaluation rendered {baseline_verdict.value}.")
