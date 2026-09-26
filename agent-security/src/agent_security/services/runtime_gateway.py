"""Security boundary for action evaluation and the harmless demonstration tool."""

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from agent_security.domain.runtime import RuntimeActionInput, RuntimeDecision


@dataclass(frozen=True)
class AuthenticatedAgent:
    organization_id: str
    project_id: str
    agent_id: str
    status: str


@dataclass
class StoredAction:
    action_id: str
    identity: AuthenticatedAgent
    session_id: str
    normalized: dict[str, Any]
    digest: str
    decision: str
    correlation_id: str
    created_at: datetime


class RuntimeGateway:
    """Deterministic evaluator; callers persist the returned records themselves."""

    policy_id = "runtime-default-v1"
    policy_version = 1

    def __init__(self, signing_key: str, authorization_ttl_seconds: int = 120):
        self._key = signing_key.encode("utf-8")
        self._ttl = authorization_ttl_seconds

    @staticmethod
    def normalize(identity: AuthenticatedAgent, request: RuntimeActionInput) -> dict[str, Any]:
        """Build the stable representation; client identity fields are never accepted."""
        return {
            "agent_id": identity.agent_id,
            "arguments": request.arguments,
            "destination": (request.destination or "").strip().lower() or None,
            "operation": request.operation.strip().lower().replace(" ", "_"),
            "organization_id": identity.organization_id,
            "project_id": identity.project_id,
            "resource": request.resource.strip().lower(),
            "session_id": request.session_id,
            "tool": request.tool.strip().lower().replace(" ", "_"),
        }

    @staticmethod
    def digest(normalized: dict[str, Any]) -> str:
        payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def evaluate(self, identity: AuthenticatedAgent, request: RuntimeActionInput, correlation_id: str) -> tuple[StoredAction, RuntimeDecision]:
        normalized = self.normalize(identity, request)
        digest = self.digest(normalized)
        action_id = "act_" + uuid.uuid4().hex
        decision, reason_code, explanation, signals = self._policy(identity, normalized)
        action = StoredAction(action_id, identity, request.session_id, normalized, digest, decision, correlation_id, datetime.now(timezone.utc))
        token, expires_at = (None, None)
        if decision == "ALLOW":
            token, expires_at = self.issue_authorization(action)
        return action, RuntimeDecision(
            action_id=action_id, decision=decision, policy_id=self.policy_id,
            policy_version=self.policy_version, reason_code=reason_code,
            explanation=explanation, risk_signals=signals, action_digest=digest,
            correlation_id=correlation_id, execution_authorization=token,
            execution_authorization_expires_at=expires_at,
        )

    def _policy(self, identity: AuthenticatedAgent, action: dict[str, Any]) -> tuple[str, str, str, list[str]]:
        if identity.status == "suspended":
            return "SUSPEND", "AGENT_SUSPENDED", "The authenticated agent is suspended.", ["agent_suspended"]
        if identity.status != "active":
            return "BLOCK", "AGENT_INACTIVE", "The authenticated agent is not active.", ["agent_inactive"]
        if action["operation"] in {"delete", "drop", "destroy"}:
            return "BLOCK", "DESTRUCTIVE_OPERATION", "Destructive operations are blocked by the default runtime policy.", ["destructive_operation"]
        if action["tool"] in {"external", "http"} and action["operation"] in {"send", "post", "write"}:
            return "BLOCK", "EXTERNAL_EGRESS_BLOCKED", "External egress is blocked by the default runtime policy.", ["external_egress"]
        if action["resource"].startswith(("secrets", "credentials", "forbidden")):
            return "BLOCK", "RESOURCE_NOT_PERMITTED", "The requested resource is not permitted.", ["unauthorized_resource"]
        if action["operation"] in {"write", "update"} and action["tool"] not in {"safe_echo"}:
            return "REQUIRE_APPROVAL", "PRODUCTION_MUTATION", "The mutation requires approval before execution.", ["mutation"]
        return "ALLOW", "ACTION_PERMITTED", "The normalized action is permitted by the default runtime policy.", []

    def issue_authorization(self, action: StoredAction) -> tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._ttl)
        claims = {"aid": action.action_id, "agent": action.identity.agent_id, "org": action.identity.organization_id,
                  "session": action.session_id, "digest": action.digest, "policy": self.policy_version,
                  "exp": int(expires_at.timestamp()), "nonce": secrets.token_urlsafe(12)}
        encoded = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
        signature = hmac.new(self._key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"rta1.{encoded}.{signature}", expires_at

    def verify_authorization(self, token: str, action: StoredAction, identity: AuthenticatedAgent) -> bool:
        try:
            prefix, encoded, signature = token.split(".")
            if prefix != "rta1" or not hmac.compare_digest(signature, hmac.new(self._key, encoded.encode(), hashlib.sha256).hexdigest()):
                return False
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            return (claims["exp"] >= int(datetime.now(timezone.utc).timestamp()) and claims["aid"] == action.action_id
                    and claims["agent"] == identity.agent_id and claims["org"] == identity.organization_id
                    and claims["session"] == action.session_id and claims["digest"] == action.digest
                    and claims["policy"] == self.policy_version)
        except (ValueError, KeyError, json.JSONDecodeError):
            return False

    @staticmethod
    def execute_safe_echo(action: StoredAction) -> dict[str, Any]:
        """Harmless protected tool: no network or filesystem side effect occurs."""
        if action.decision != "ALLOW":
            raise ValueError("Only ALLOWED actions are permitted to execute.")
        if action.normalized["tool"] not in {"safe_echo", "database", "file"}:
            raise ValueError(f"Tool {action.normalized['tool']} is not authorized for demonstration execution.")
        return {
            "message": "safe tool executed",
            "tool": action.normalized["tool"],
            "operation": action.normalized["operation"],
            "resource": action.normalized["resource"],
            "action_id": action.action_id,
        }
