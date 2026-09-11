"""Unit Tests for Execution Lifecycle State Machine and Policy Decoupling."""

import pytest
from agent_security.core.state_machine import (
    InvalidStateTransitionError,
    PolicyViolationTransitionError,
    validate_transition,
)
from agent_security.domain.enums import ExecutionState, PolicyDecision


def test_standard_allow_lifecycle():
    """Verify happy-path execution lifecycle for an ALLOW decision."""
    decision = PolicyDecision.ALLOW
    
    # SUBMITTED -> SCHEDULED
    validate_transition(ExecutionState.SUBMITTED, ExecutionState.SCHEDULED, decision)
    
    # SCHEDULED -> EXECUTING
    validate_transition(ExecutionState.SCHEDULED, ExecutionState.EXECUTING, decision)
    
    # EXECUTING -> SUCCEEDED
    validate_transition(ExecutionState.EXECUTING, ExecutionState.SUCCEEDED, decision)


def test_require_approval_lifecycle():
    """Verify lifecycle for an action requiring human approval."""
    decision = PolicyDecision.REQUIRE_APPROVAL

    # SUBMITTED -> AWAITING_APPROVAL
    validate_transition(ExecutionState.SUBMITTED, ExecutionState.AWAITING_APPROVAL, decision)

    # AWAITING_APPROVAL -> APPROVED
    validate_transition(ExecutionState.AWAITING_APPROVAL, ExecutionState.APPROVED, decision)

    # APPROVED -> SCHEDULED
    validate_transition(ExecutionState.APPROVED, ExecutionState.SCHEDULED, decision)

    # SCHEDULED -> EXECUTING
    validate_transition(ExecutionState.SCHEDULED, ExecutionState.EXECUTING, decision)

    # EXECUTING -> SUCCEEDED
    validate_transition(ExecutionState.EXECUTING, ExecutionState.SUCCEEDED, decision)


def test_require_approval_cannot_bypass_to_scheduled():
    """Verify that a REQUIRE_APPROVAL action cannot jump directly to SCHEDULED."""
    decision = PolicyDecision.REQUIRE_APPROVAL
    with pytest.raises(PolicyViolationTransitionError):
        validate_transition(ExecutionState.SUBMITTED, ExecutionState.SCHEDULED, decision)


def test_blocked_action_cannot_execute():
    """Verify that a BLOCK or SUSPEND decision cannot transition to SCHEDULED or EXECUTING."""
    for decision in (PolicyDecision.BLOCK, PolicyDecision.SUSPEND):
        # Can transition to REJECTED
        validate_transition(ExecutionState.SUBMITTED, ExecutionState.REJECTED, decision)

        # Cannot transition to SCHEDULED
        with pytest.raises(PolicyViolationTransitionError):
            validate_transition(ExecutionState.SUBMITTED, ExecutionState.SCHEDULED, decision)


def test_cannot_transition_out_of_terminal_state():
    """Verify that terminal states (SUCCEEDED, FAILED, REJECTED, CANCELLED) cannot transition."""
    decision = PolicyDecision.ALLOW
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(ExecutionState.SUCCEEDED, ExecutionState.EXECUTING, decision)
    
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(ExecutionState.REJECTED, ExecutionState.SCHEDULED, decision)
