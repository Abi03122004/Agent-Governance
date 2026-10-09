"""Execution Lifecycle State Machine and Invariant Enforcement."""

from typing import Set, Tuple
from agent_security.domain.enums import ExecutionState, PolicyDecision


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal execution state transition is attempted."""
    pass


class PolicyViolationTransitionError(ValueError):
    """Raised when an execution state transition violates the active Policy Decision."""
    pass


# Allowed baseline transitions (from_state, to_state)
VALID_TRANSITIONS: Set[Tuple[ExecutionState, ExecutionState]] = {
    (ExecutionState.SUBMITTED, ExecutionState.AWAITING_APPROVAL),
    (ExecutionState.SUBMITTED, ExecutionState.SCHEDULED),
    (ExecutionState.SUBMITTED, ExecutionState.REJECTED),
    (ExecutionState.AWAITING_APPROVAL, ExecutionState.APPROVED),
    (ExecutionState.AWAITING_APPROVAL, ExecutionState.REJECTED),
    (ExecutionState.APPROVED, ExecutionState.SCHEDULED),
    (ExecutionState.SCHEDULED, ExecutionState.EXECUTING),
    (ExecutionState.EXECUTING, ExecutionState.SUCCEEDED),
    (ExecutionState.EXECUTING, ExecutionState.FAILED),
    # Cancellation can happen from any non-terminal state
    (ExecutionState.SUBMITTED, ExecutionState.CANCELLED),
    (ExecutionState.AWAITING_APPROVAL, ExecutionState.CANCELLED),
    (ExecutionState.APPROVED, ExecutionState.CANCELLED),
    (ExecutionState.SCHEDULED, ExecutionState.CANCELLED),
}

TERMINAL_STATES = {
    ExecutionState.SUCCEEDED,
    ExecutionState.FAILED,
    ExecutionState.REJECTED,
    ExecutionState.CANCELLED,
}


def validate_transition(
    current_state: ExecutionState,
    target_state: ExecutionState,
    policy_decision: PolicyDecision,
) -> None:
    """Validate that moving from current_state to target_state is legally permissible
    under both state machine rules and the governing PolicyDecision.
    """
    if current_state in TERMINAL_STATES:
        raise InvalidStateTransitionError(
            f"Cannot transition from terminal state {current_state} to {target_state}."
        )

    if (current_state, target_state) not in VALID_TRANSITIONS:
        raise InvalidStateTransitionError(
            f"Illegal state transition from {current_state} to {target_state}."
        )

    # Invariants tied to PolicyDecision
    if policy_decision in (PolicyDecision.BLOCK, PolicyDecision.SUSPEND):
        if target_state not in (ExecutionState.REJECTED, ExecutionState.CANCELLED):
            raise PolicyViolationTransitionError(
                f"Action blocked or suspended by policy ({policy_decision}); "
                f"cannot transition to {target_state}."
            )

    if policy_decision == PolicyDecision.REQUIRE_APPROVAL:
        # A REQUIRE_APPROVAL action can never directly enter SCHEDULED or EXECUTING from SUBMITTED
        if current_state == ExecutionState.SUBMITTED and target_state == ExecutionState.SCHEDULED:
            raise PolicyViolationTransitionError(
                "Action requires approval; cannot jump directly to SCHEDULED without being APPROVED."
            )

    if policy_decision == PolicyDecision.ALLOW:
        # An ALLOW action cannot be sent to AWAITING_APPROVAL
        if target_state == ExecutionState.AWAITING_APPROVAL:
            raise PolicyViolationTransitionError(
                "Action is explicitly ALLOWed by policy; cannot enter AWAITING_APPROVAL."
            )
