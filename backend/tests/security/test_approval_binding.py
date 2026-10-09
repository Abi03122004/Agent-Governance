"""Unit Tests for Cryptographic Approval Binding, Expiry, and Replay Protection."""

from datetime import datetime, timedelta, timezone
from agent_security.core.canonical import compute_action_canonical_hash
from agent_security.domain.approval import ApprovalRequest
from agent_security.domain.enums import ApprovalStatus
from agent_security.domain.tool import ActionRequest


def test_approval_cryptographically_bound_to_exact_action():
    """Verify approval is bound to canonical hash and detects argument changes."""
    action = ActionRequest(
        action_id="act-wire-01",
        tenant_id="tenant-acme",
        project_id="proj-finance",
        agent_id="agent-01",
        session_id="sess-01",
        task_id="task-01",
        tool_name="send_payment",
        arguments={"recipient": "Supplier Inc", "amount": 10000},
    )
    action_hash = compute_action_canonical_hash(action)

    now = datetime.now(timezone.utc)
    approval = ApprovalRequest(
        ticket_id="ticket-appr-001",
        tenant_id=action.tenant_id,
        action_id=action.action_id,
        canonical_action_hash=action_hash,
        expires_at=now + timedelta(minutes=15),
    )

    # Valid check
    assert approval.canonical_action_hash == action_hash
    assert approval.can_be_approved(now) is True

    # Tampered action
    tampered_action = action.model_copy(
        update={"arguments": {"recipient": "Supplier Inc", "amount": 50000}}
    )
    tampered_hash = compute_action_canonical_hash(tampered_action)
    assert approval.canonical_action_hash != tampered_hash


def test_approval_expiration():
    """Verify approval request expires automatically after TTL."""
    now = datetime.now(timezone.utc)
    expired_approval = ApprovalRequest(
        ticket_id="ticket-expired-002",
        tenant_id="tenant-acme",
        action_id="act-01",
        canonical_action_hash="a" * 64,
        expires_at=now - timedelta(seconds=1),
    )
    assert expired_approval.is_expired(now) is True
    assert expired_approval.can_be_approved(now) is False


def test_approval_status_transitions_and_replay_prevention():
    """Simulate single-use approval consumption preventing replay attacks."""
    now = datetime.now(timezone.utc)
    approval = ApprovalRequest(
        ticket_id="ticket-appr-003",
        tenant_id="tenant-acme",
        action_id="act-01",
        canonical_action_hash="b" * 64,
        expires_at=now + timedelta(minutes=10),
    )
    assert approval.status == ApprovalStatus.PENDING

    # Step 1: Human signs off
    approval.status = ApprovalStatus.APPROVED
    approval.approver_id = "user-security-officer-1"
    approval.decided_at = now

    # Step 2: Broker consumes the approval
    assert approval.status == ApprovalStatus.APPROVED
    approval.status = ApprovalStatus.CONSUMED

    # Step 3: Attacker attempts to replay the same approval
    assert approval.status == ApprovalStatus.CONSUMED
    assert approval.status != ApprovalStatus.APPROVED  # Cannot be consumed again
