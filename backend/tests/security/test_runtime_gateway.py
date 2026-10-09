from agent_security.domain.runtime import RuntimeActionInput
from agent_security.services.runtime_gateway import AuthenticatedAgent, RuntimeGateway


def agent(status="active"):
    return AuthenticatedAgent("org_alpha", "proj_finance", "finance_agent", status)


def action(**changes):
    values = {"session_id": "sess_123", "tool": "safe_echo", "operation": "read", "resource": "transactions"}
    values.update(changes)
    return RuntimeActionInput(**values)


def test_permitted_action_authorizes_and_executes_safe_tool():
    gateway = RuntimeGateway("test-signing-key-that-is-long-enough", 120)
    stored, decision = gateway.evaluate(agent(), action(), "req_123")
    assert decision.decision == "ALLOW"
    assert gateway.verify_authorization(decision.execution_authorization, stored, agent())
    assert gateway.execute_safe_echo(stored)["message"] == "safe tool executed"


def test_blocked_action_has_no_authorization_and_never_executes():
    gateway = RuntimeGateway("test-signing-key-that-is-long-enough", 120)
    stored, decision = gateway.evaluate(agent(), action(tool="database", operation="delete"), "req_123")
    assert decision.decision == "BLOCK"
    assert decision.execution_authorization is None
    try:
        gateway.execute_safe_echo(stored)
    except ValueError:
        pass
    else:
        raise AssertionError("Blocked action reached the protected tool")


def test_identity_fields_are_not_client_controlled_and_digest_is_deterministic():
    gateway = RuntimeGateway("test-signing-key-that-is-long-enough", 120)
    first, _ = gateway.evaluate(agent(), action(arguments={"b": 2, "a": 1}), "req_a")
    second, _ = gateway.evaluate(agent(), action(arguments={"a": 1, "b": 2}), "req_b")
    assert first.normalized["agent_id"] == "finance_agent"
    assert first.digest == second.digest


def test_authorization_cannot_be_transferred_to_another_agent_or_action():
    gateway = RuntimeGateway("test-signing-key-that-is-long-enough", 120)
    first, decision = gateway.evaluate(agent(), action(), "req_123")
    other, _ = gateway.evaluate(agent(), action(resource="other"), "req_124")
    assert not gateway.verify_authorization(decision.execution_authorization, other, agent())
    assert not gateway.verify_authorization(decision.execution_authorization, first, AuthenticatedAgent("org_alpha", "proj_finance", "support_agent", "active"))


def test_policy_decisions_include_block_approval_and_suspend():
    gateway = RuntimeGateway("test-signing-key-that-is-long-enough", 120)
    assert gateway.evaluate(agent(), action(tool="database", operation="delete"), "req")[1].decision == "BLOCK"
    assert gateway.evaluate(agent(), action(tool="deployment", operation="update"), "req")[1].decision == "REQUIRE_APPROVAL"
    assert gateway.evaluate(agent("suspended"), action(), "req")[1].decision == "SUSPEND"
