"""Unit Tests for Deterministic Canonical JSON and Cryptographic Action Hashing."""

from datetime import datetime, timezone
from agent_security.core.canonical import (
    compute_action_canonical_hash,
    verify_action_hash,
)
from agent_security.domain.tool import ActionRequest


def test_canonical_hash_is_invariant_to_argument_key_order():
    """Verify that different dictionary key ordering produces the exact same hash."""
    action_1 = ActionRequest(
        action_id="act-001",
        tenant_id="tenant-acme",
        project_id="proj-finance",
        agent_id="agent-trader",
        session_id="sess-alpha-001",
        task_id="task-wire-transfer",
        tool_name="wire_transfer",
        arguments={"amount": 1000, "recipient": "Alice", "currency": "USD"},
    )

    action_2 = ActionRequest(
        action_id="act-001",
        tenant_id="tenant-acme",
        project_id="proj-finance",
        agent_id="agent-trader",
        session_id="sess-alpha-001",
        task_id="task-wire-transfer",
        tool_name="wire_transfer",
        arguments={"currency": "USD", "amount": 1000, "recipient": "Alice"},
    )

    hash_1 = compute_action_canonical_hash(action_1)
    hash_2 = compute_action_canonical_hash(action_2)

    assert hash_1 == hash_2
    assert len(hash_1) == 64
    assert verify_action_hash(action_1, hash_2) is True


def test_argument_tampering_changes_canonical_hash():
    """Verify that any modification of arguments changes the hash (TOCTOU protection)."""
    original_action = ActionRequest(
        action_id="act-001",
        tenant_id="tenant-acme",
        project_id="proj-finance",
        agent_id="agent-trader",
        session_id="sess-alpha-001",
        task_id="task-wire-transfer",
        tool_name="wire_transfer",
        arguments={"amount": 1000, "recipient": "Alice"},
    )

    tampered_action = ActionRequest(
        action_id="act-001",
        tenant_id="tenant-acme",
        project_id="proj-finance",
        agent_id="agent-trader",
        session_id="sess-alpha-001",
        task_id="task-wire-transfer",
        tool_name="wire_transfer",
        arguments={"amount": 100000, "recipient": "Eve"},
    )

    original_hash = compute_action_canonical_hash(original_action)
    tampered_hash = compute_action_canonical_hash(tampered_action)

    assert original_hash != tampered_hash
    assert verify_action_hash(tampered_action, original_hash) is False
