"""Policy Engine Orchestrator."""

from typing import List, Optional, Tuple
from agent_security.domain.enums import PolicyDecision
from agent_security.policies.rules import DEFAULT_RULES, DeterministicRule
from agent_security.policies.evaluator import DecisionSynthesisEngine


class PolicyEngine:
    """Core deterministic policy engine."""

    def __init__(self, rules: Optional[List[DeterministicRule]] = None):
        self.rules = sorted(rules or DEFAULT_RULES, key=lambda r: r.priority)

    def evaluate_action(self, tool: str, operation: str) -> Tuple[PolicyDecision, str]:
        """Match against ordered deterministic rules."""
        for rule in self.rules:
            if rule.matches(tool, operation):
                return rule.decision, f"Rule '{rule.name}' matched with decision {rule.decision.value}."
        # Default policy: fail-secure block unknown actions
        return PolicyDecision.BLOCK, "Default fail-secure: No policy rule matched the action."
