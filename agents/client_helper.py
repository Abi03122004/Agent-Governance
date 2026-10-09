"""Helper module for autonomous agents to obtain credentials from the control plane."""

import os
import requests

BASE_URL = os.getenv("GOVERNANCE_URL", "http://localhost:8000")
ADMIN_USER = "security_admin@enterprise.internal"
ADMIN_HEADERS = {"X-User-Email": ADMIN_USER}


def get_or_create_agent_credential(agent_id: str, name: str, purpose: str) -> str:
    """Returns AGENT_CREDENTIAL env var if present, else bootstraps the agent with the control plane."""
    env_token = os.environ.get("AGENT_CREDENTIAL")
    if env_token:
        return env_token

    # 1. Ensure user
    try:
        requests.post(
            f"{BASE_URL}/api/v1/users",
            json={"id": "usr_admin", "email": ADMIN_USER, "display_name": "Security Officer"},
            timeout=5,
        )
    except Exception:
        pass

    # 2. Ensure organization
    try:
        requests.post(
            f"{BASE_URL}/api/v1/organizations",
            json={"id": "org_enterprise", "name": "Enterprise Autonomous Fleet"},
            timeout=5,
        )
    except Exception:
        pass

    # 3. Ensure membership
    try:
        requests.post(
            f"{BASE_URL}/api/v1/users/memberships",
            json={
                "id": "mem_admin_01",
                "user_id": "usr_admin",
                "organization_id": "org_enterprise",
                "role": "administrator",
            },
            timeout=5,
        )
    except Exception:
        pass

    # 4. Ensure project
    try:
        requests.post(
            f"{BASE_URL}/api/v1/projects",
            json={"id": "proj_operations", "organization_id": "org_enterprise", "name": "Core Ops"},
            timeout=5,
        )
    except Exception:
        pass

    # 5. Register agent
    try:
        requests.post(
            f"{BASE_URL}/api/v1/agents",
            headers=ADMIN_HEADERS,
            json={
                "id": agent_id,
                "organization_id": "org_enterprise",
                "project_id": "proj_operations",
                "name": name,
                "environment": "production",
                "purpose": purpose,
            },
            timeout=5,
        )
    except Exception:
        pass

    # 6. Issue fresh credential
    resp = requests.post(
        f"{BASE_URL}/api/v1/agents/{agent_id}/credentials",
        headers=ADMIN_HEADERS,
        timeout=5,
    )
    if resp.status_code == 201:
        return resp.json()["plaintext_secret"]
    raise RuntimeError(f"Unable to issue credentials for agent {agent_id}: {resp.text}")
