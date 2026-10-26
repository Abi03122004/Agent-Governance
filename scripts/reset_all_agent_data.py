"""Reset All Agent Data and Historical Records.

Safely backs up and completely removes all agents, credentials, sessions,
runtime actions, approval history, execution records, and audit events,
resetting the platform to a completely clean slate with 0 agents.

Preserves the primary organization ('org_enterprise'), admin user ('usr_admin'),
and default project ('proj_operations') so you can immediately register
your own custom agents via the Dashboard or API.

Usage:
    python scripts/reset_all_agent_data.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKUP_DIR = Path(__file__).resolve().parent / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = int(time.time())
BACKUP_FILE = BACKUP_DIR / f"full_agent_data_backup_{TIMESTAMP}.json"


def run_psql(query: str) -> str:
    """Run a query inside the PostgreSQL container via docker compose."""
    cmd = [
        "docker", "compose", "exec", "-T", "postgres",
        "psql", "-U", "postgres", "-d", "agent_governance",
        "-t", "-A", "-c", query
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def run_psql_json(table: str) -> list:
    """Fetch all rows from a table as JSON."""
    query = f"SELECT json_agg(t) FROM (SELECT * FROM {table}) t;"
    cmd = [
        "docker", "compose", "exec", "-T", "postgres",
        "psql", "-U", "postgres", "-d", "agent_governance",
        "-t", "-A", "-c", query
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    raw = res.stdout.strip()
    if raw and raw != "":
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


def main():
    print("=" * 70)
    print("RESETTING ALL AGENT DATA & PURGING TO ZERO AGENTS")
    print("=" * 70)

    tables_to_backup = [
        "agents",
        "agent_credentials",
        "agent_sessions",
        "approval_requests",
        "runtime_actions",
        "execution_authorizations",
        "execution_records",
        "audit_events",
        "organizations",
        "projects",
        "users",
        "memberships",
    ]

    # Step 1: Backup all data to JSON
    print("\n[Step 1] Creating full safety backup of existing records...")
    backup_data = {}
    for tbl in tables_to_backup:
        rows = run_psql_json(tbl)
        backup_data[tbl] = rows
        print(f" -> Backed up {len(rows):>3} rows from '{tbl}'")

    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, default=str)
    print(f"\n [+] Safety backup saved successfully to:\n     {BACKUP_FILE}")

    # Step 2: Clean all agent data and actions
    print("\n[Step 2] Purging all agent identities, credentials, sessions, approvals, and actions...")
    cleanup_sql = """
    BEGIN;

    -- 1. Remove all execution records and authorizations
    DELETE FROM execution_records;
    DELETE FROM execution_authorizations;

    -- 2. Remove all approval requests and history
    DELETE FROM approval_requests;

    -- 3. Remove all runtime actions
    DELETE FROM runtime_actions;

    -- 4. Remove all audit events
    DELETE FROM audit_events;

    -- 5. Remove all agent sessions
    DELETE FROM agent_sessions;

    -- 6. Remove all agent credentials
    DELETE FROM agent_credentials;

    -- 7. Remove all agents
    DELETE FROM agents;

    -- 8. Clean up test organizations, test projects, test memberships, and test users
    DELETE FROM memberships WHERE organization_id LIKE 'org_test_%';
    DELETE FROM projects WHERE organization_id LIKE 'org_test_%';
    DELETE FROM organizations WHERE id LIKE 'org_test_%';
    DELETE FROM users WHERE id IN ('user_admin_e2e', 'user_reviewer_ops');

    -- 9. Ensure primary default organization exists
    INSERT INTO organizations (id, name, created_at, updated_at)
    VALUES ('org_enterprise', 'Enterprise Workspace', NOW(), NOW())
    ON CONFLICT (id) DO UPDATE SET name = 'Enterprise Workspace';

    -- 10. Ensure default admin user and reviewer exist
    INSERT INTO users (id, email, display_name, status, created_at, updated_at)
    VALUES 
        ('usr_admin', 'security_admin@enterprise.internal', 'Security Administrator', 'active', NOW(), NOW()),
        ('usr_reviewer', 'reviewer@enterprise.internal', 'Senior Reviewer', 'active', NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;

    -- 11. Ensure memberships in org_enterprise
    INSERT INTO memberships (id, user_id, organization_id, role, created_at)
    VALUES 
        ('mem_admin_01', 'usr_admin', 'org_enterprise', 'administrator', NOW()),
        ('mem_reviewer_01', 'usr_reviewer', 'org_enterprise', 'approver', NOW())
    ON CONFLICT (id) DO NOTHING;

    -- 12. Ensure default project exists
    INSERT INTO projects (id, organization_id, name, status, created_at, updated_at)
    VALUES ('proj_operations', 'org_enterprise', 'Default Project', 'active', NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;

    COMMIT;
    """

    res = run_psql(cleanup_sql)
    print(f" [+] Database cleanup result: {res}")

    # Step 3: Flush Redis cache
    print("\n[Step 3] Flushing Redis cache...")
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "FLUSHALL"],
        capture_output=True, text=True, check=True
    )
    print(" [+] Redis cache flushed.")

    # Step 4: Verification of 0 state
    print("\n[Step 4] Verifying clean zero-state in PostgreSQL...")
    agent_count = int(run_psql("SELECT COUNT(*) FROM agents;"))
    action_count = int(run_psql("SELECT COUNT(*) FROM runtime_actions;"))
    approval_count = int(run_psql("SELECT COUNT(*) FROM approval_requests;"))
    cred_count = int(run_psql("SELECT COUNT(*) FROM agent_credentials;"))
    session_count = int(run_psql("SELECT COUNT(*) FROM agent_sessions;"))
    audit_count = int(run_psql("SELECT COUNT(*) FROM audit_events;"))
    org_count = int(run_psql("SELECT COUNT(*) FROM organizations;"))

    print(f" Agents in DB             : {agent_count} (Expected: 0)")
    print(f" Runtime Actions in DB    : {action_count} (Expected: 0)")
    print(f" Approvals in DB          : {approval_count} (Expected: 0)")
    print(f" Credentials in DB        : {cred_count} (Expected: 0)")
    print(f" Sessions in DB           : {session_count} (Expected: 0)")
    print(f" Audit Events in DB       : {audit_count} (Expected: 0)")
    print(f" Active Organizations     : {org_count} (Default: 1 - 'org_enterprise')")

    assert agent_count == 0, f"Expected 0 agents, found {agent_count}"
    assert action_count == 0, f"Expected 0 actions, found {action_count}"
    assert approval_count == 0, f"Expected 0 approvals, found {approval_count}"

    print("\n" + "=" * 70)
    print("SUCCESS: ALL AGENT DATA RESET TO ZERO!")
    print("You can now open http://localhost:3000/agents and click '+ Add Agent'")
    print("to register your own real agents.")
    print("=" * 70)


if __name__ == "__main__":
    main()
