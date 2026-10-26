import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.config import get_settings
from agent_security.db.models.session import AgentSessionModel
from agent_security.db.models.agent import AgentModel
from agent_security.security.context import AuthenticatedAgent


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_user_token(
    user_id: str,
    email: str,
    role: Optional[str] = None,
    expires_in_seconds: int = 3600,
    secret_key: Optional[str] = None,
) -> str:
    """Issue a cryptographically signed HMAC-SHA256 JWT for user authentication."""
    key = (secret_key or get_settings().SECRET_KEY).encode("utf-8")
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    if role:
        payload["role"] = role

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_user_token(token: str, secret_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Verify that a user JWT is cryptographically authentic, unexpired, and valid."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        key = (secret_key or get_settings().SECRET_KEY).encode("utf-8")
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        now = int(time.time())
        if payload.get("exp", 0) < now:
            return None
        return payload
    except Exception:
        return None


async def authenticate_session(
    session_token: str,
    db: AsyncSession,
) -> Optional[AuthenticatedAgent]:
    """Validate a session token and resolve the bound agent identity."""
    stmt = (
        select(AgentSessionModel, AgentModel)
        .join(AgentModel, AgentSessionModel.agent_id == AgentModel.id)
        .where(
            AgentSessionModel.session_id == session_token,
            AgentSessionModel.status == "active",
        )
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        return None

    session, agent = row
    return AuthenticatedAgent(
        organization_id=session.organization_id,
        project_id=session.project_id,
        agent_id=session.agent_id,
        status=agent.status,
    )

