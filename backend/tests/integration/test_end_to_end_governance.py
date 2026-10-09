"""Comprehensive End-to-End Governance and Security Invariants Tests."""

import hashlib
import time
from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import MagicMock

from agent_security.services.runtime_gateway import AuthenticatedAgent, RuntimeGateway, StoredAction
from agent_security.domain.runtime import RuntimeActionInput
from agent_security.core.canonical import compute_action_canonical_hash
from agent_security.domain.tool import ActionRequest


def test_agent_separation_and_tenant_isolation():
    """Verify that multiple agents maintain distinct identities and tenant scopes."""
    finance_agent = AuthenticatedAgent(
        organization_id="org_fintech",
        project_id="proj_ledger",
        agent_id="agt_finance_01",
        status="active",
    )
    support_agent = AuthenticatedAgent(
        organization_id="org_support",
        project_id="proj_crm",
        agent_id="agt_support_02",
        status="active",
    )

    gateway = RuntimeGateway("test-signing-key-governance-platform-32chars", 120)

    # 1. Normalized actions retain authenticated identity, never trusting client parameters
    fin_req = RuntimeActionInput(
        session_id="sess_fin_01",
        tool="database",
        operation="read",
        resource="accounts",
    )
    supp_req = RuntimeActionInput(
        session_id="sess_supp_01",
        tool="database",
        operation="read",
        resource="tickets",
    )

    fin_stored, fin_dec = gateway.evaluate(finance_agent, fin_req, "corr_1")
    supp_stored, supp_dec = gateway.evaluate(support_agent, supp_req, "corr_2")

    assert fin_stored.identity.organization_id == "org_fintech"
    assert fin_stored.identity.agent_id == "agt_finance_01"
    assert supp_stored.identity.organization_id == "org_support"
    assert supp_stored.identity.agent_id == "agt_support_02"

    # 2. Finance agent execution authorization CANNOT be used by Support agent
    assert gateway.verify_authorization(fin_dec.execution_authorization, fin_stored, finance_agent) is True
    assert gateway.verify_authorization(fin_dec.execution_authorization, fin_stored, support_agent) is False
    assert gateway.verify_authorization(fin_dec.execution_authorization, supp_stored, finance_agent) is False


def test_enforcement_blocked_tool_execution_count_remains_zero():
    """CRITICAL SECURITY INVARIANT:

    A blocked action MUST NOT execute. Tool execution count MUST remain 0.
    """
    gateway = RuntimeGateway("test-signing-key-governance-platform-32chars", 120)
    agent = AuthenticatedAgent("org_corp", "proj_ops", "agt_devops", "active")

    # Action: database delete (blocked by default policy)
    req = RuntimeActionInput(
        session_id="sess_ops",
        tool="database",
        operation="delete",
        resource="production_clusters",
    )

    stored, decision = gateway.evaluate(agent, req, "corr_block")

    # 1. Policy verdict must be BLOCK
    assert decision.decision == "BLOCK"
    assert decision.execution_authorization is None

    # 2. Mock external tool counter
    tool_mock = MagicMock()

    # 3. Attempting to execute via runtime gateway must be rejected and tool counter remains ZERO
    try:
        gateway.execute_safe_echo(stored)
        tool_mock()  # Should never be reached
    except ValueError:
        pass  # Expected rejection

    assert tool_mock.call_count == 0, "Security Violation: Blocked action executed tool!"


def test_require_approval_prevents_automatic_execution():
    """Mutations in production require human approval and do not receive automatic execution auth."""
    gateway = RuntimeGateway("test-signing-key-governance-platform-32chars", 120)
    agent = AuthenticatedAgent("org_corp", "proj_ops", "agt_devops", "active")

    req = RuntimeActionInput(
        session_id="sess_ops",
        tool="database",
        operation="update",
        resource="records",
    )

    stored, decision = gateway.evaluate(agent, req, "corr_appr")
    assert decision.decision == "REQUIRE_APPROVAL"
    assert decision.execution_authorization is None

    try:
        gateway.execute_safe_echo(stored)
        raise AssertionError("Unapproved action executed tool!")
    except ValueError:
        pass


def test_suspended_agent_blocked_immediately():
    """Kill Switch: Suspended agents cannot execute any actions."""
    gateway = RuntimeGateway("test-signing-key-governance-platform-32chars", 120)
    agent = AuthenticatedAgent("org_corp", "proj_ops", "agt_suspended", "suspended")

    req = RuntimeActionInput(
        session_id="sess_ops",
        tool="safe_echo",
        operation="read",
        resource="status",
    )

    stored, decision = gateway.evaluate(agent, req, "corr_sus")
    assert decision.decision == "SUSPEND"
    assert decision.execution_authorization is None


def test_expired_execution_authorization_is_rejected():
    """Execution authorization must expire and reject stale execution."""
    # Gateway with 1 second TTL
    gateway = RuntimeGateway("test-signing-key-governance-platform-32chars", authorization_ttl_seconds=-1)
    agent = AuthenticatedAgent("org_corp", "proj_ops", "agt_timer", "active")

    req = RuntimeActionInput(
        session_id="sess_ops",
        tool="safe_echo",
        operation="read",
        resource="data",
    )

    stored, decision = gateway.evaluate(agent, req, "corr_exp")
    assert decision.decision == "ALLOW"
    # Because TTL is negative, token is already expired
    assert gateway.verify_authorization(decision.execution_authorization, stored, agent) is False


def test_action_digest_deterministic_and_tamper_resistant():
    """Verify SHA-256 canonical hashing invariance and tamper resistance."""
    action_1 = ActionRequest(
        action_id="act_hash_1",
        organization_id="org_test",
        project_id="proj_test",
        agent_id="agt_1",
        session_id="sess_1",
        tool="safe_echo",
        arguments={"amount": 100, "user": "alice", "active": True},
    )
    action_2 = ActionRequest(
        action_id="act_hash_2",
        organization_id="org_test",
        project_id="proj_test",
        agent_id="agt_1",
        session_id="sess_1",
        tool="safe_echo",
        arguments={"active": True, "amount": 100, "user": "alice"},  # reordered keys
    )

    digest_1 = compute_action_canonical_hash(action_1)
    digest_2 = compute_action_canonical_hash(action_2)

    assert digest_1 == digest_2
    assert len(digest_1) == 64

    # Tamper with an argument
    tampered = action_1.model_copy(update={"arguments": {"amount": 999999, "user": "alice", "active": True}})
    digest_tampered = compute_action_canonical_hash(tampered)
    assert digest_1 != digest_tampered
