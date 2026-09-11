"""Unit Tests for Database Models and SQLAlchemy Metadata."""

from agent_security.db.models import Base


def test_metadata_contains_all_core_tables():
    """Verify all 10 core tables are defined in the metadata."""
    expected_tables = {
        "tenants",
        "projects",
        "agents",
        "agent_sessions",
        "tools",
        "policies",
        "policy_rules",
        "approval_requests",
        "execution_records",
        "audit_events",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables)


def test_tenants_table_structure():
    table = Base.metadata.tables["tenants"]
    assert "id" in table.columns
    assert "name" in table.columns
    assert "is_active" in table.columns
    assert "created_at" in table.columns
    assert table.columns["id"].primary_key is True


def test_audit_events_table_structure():
    table = Base.metadata.tables["audit_events"]
    assert "event_id" in table.columns
    assert "tenant_id" in table.columns
    assert "canonical_action_hash" in table.columns
    assert "policy_decision" in table.columns
    assert "execution_state" in table.columns
    assert "previous_event_hash" in table.columns
    assert "event_hash" in table.columns
