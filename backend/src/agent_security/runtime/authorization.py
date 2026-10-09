"""Runtime Single-Use Execution Authorizations and HMAC Verification."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Tuple

from agent_security.security.context import AuthenticatedAgent


def issue_execution_token(
    signing_key: bytes,
    action_id: str,
    identity: AuthenticatedAgent,
    session_id: str,
    digest: str,
    policy_version: int,
    ttl_seconds: int,
) -> Tuple[str, datetime]:
    """Issue a cryptographically signed execution authorization token."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    claims = {
        "aid": action_id,
        "agent": identity.agent_id,
        "org": identity.organization_id,
        "session": session_id,
        "digest": digest,
        "policy": policy_version,
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(signing_key, encoded.encode(), hashlib.sha256).hexdigest()
    return f"rta1.{encoded}.{signature}", expires_at


def verify_execution_token(
    signing_key: bytes,
    token: str,
    action_id: str,
    identity: AuthenticatedAgent,
    session_id: str,
    digest: str,
    policy_version: int,
) -> bool:
    """Verify that an execution token is cryptographically authentic and bound."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False
        prefix, encoded, signature = parts
        if prefix != "rta1":
            return False
        expected_sig = hmac.new(signing_key, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return False

        claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        now_ts = int(datetime.now(timezone.utc).timestamp())

        return (
            claims["exp"] >= now_ts
            and claims["aid"] == action_id
            and claims["agent"] == identity.agent_id
            and claims["org"] == identity.organization_id
            and claims["session"] == session_id
            and claims["digest"] == digest
            and claims["policy"] == policy_version
        )
    except Exception:
        return False
