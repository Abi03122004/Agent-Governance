"""Deterministic Policy Rules and Conditions."""

from typing import Any, Dict
from agent_security.domain.enums import PolicyDecision


class DeterministicRule:
    """Individual deterministic evaluation rule."""
    def __init__(
        self,
        rule_id: str,
        name: str,
        decision: PolicyDecision,
        tool: str,
        operation: str,
        priority: int = 100,
    ):
        self.rule_id = rule_id
        self.name = name
        self.decision = decision
        self.tool = tool
        self.operation = operation
        self.priority = priority

    def matches(self, tool: str, operation: str) -> bool:
        tool_match = self.tool == "*" or self.tool.lower() == tool.lower()
        op_match = self.operation == "*" or self.operation.lower() == operation.lower()
        return tool_match and op_match


DEFAULT_RULES = [
    # Finance database read is ALLOW
    DeterministicRule("rule_db_read", "Allow DB Read", PolicyDecision.ALLOW, "database", "read", priority=10),
    # Database delete/drop is strictly BLOCK
    DeterministicRule("rule_db_delete", "Block Destructive DB", PolicyDecision.BLOCK, "database", "delete", priority=1),
    # Production/staging deployment mutation requires human approval
    DeterministicRule("rule_deploy_mutate", "Require Approval on Deploy", PolicyDecision.REQUIRE_APPROVAL, "deployment", "mutate", priority=5),
]
