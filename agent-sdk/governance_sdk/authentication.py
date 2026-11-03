"""Governance SDK Agent Authentication."""

import os
from typing import Dict, Optional


class AgentAuthenticator:
    """Manages agent-specific bearer authentication credentials."""

    def __init__(self, agent_token: Optional[str] = None):
        token = agent_token or os.environ.get("GOVERNANCE_AGENT_TOKEN") or os.environ.get("AGENT_GOVERNANCE_TOKEN")
        if not token:
            raise ValueError(
                "Agent authentication token is required. Pass agent_token or set GOVERNANCE_AGENT_TOKEN environment variable."
            )
        self._token = token.strip()
        if not self._token.startswith("agt_"):
            # Permitted for tests or legacy tokens, but log a note
            pass

    @property
    def token(self) -> str:
        return self._token

    @property
    def masked_token(self) -> str:
        if len(self._token) <= 8:
            return "***"
        return f"{self._token[:4]}...{self._token[-4:]}"

    def get_auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "AgentGovernance-SDK/0.1.0",
        }

