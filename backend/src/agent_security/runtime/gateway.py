"""Runtime Gateway Coordinator."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from agent_security.security.context import AuthenticatedAgent
from agent_security.domain.runtime import RuntimeActionInput, RuntimeDecision
from agent_security.runtime.authorization import issue_execution_token, verify_execution_token
from agent_security.runtime.execution import execute_safe_action
from agent_security.runtime.mediation import normalize_action, compute_action_digest


@dataclass
class StoredAction:
    action_id: str
    identity: AuthenticatedAgent
    session_id: str
    normalized: Dict[str, Any]
    digest: str
    decision: str
    correlation_id: str
    created_at: datetime


class RuntimeGateway:
    """Deterministic runtime mediator and policy enforcement boundary."""

    policy_id = "runtime-default-v1"
    policy_version = 1

    def __init__(self, signing_key: str, authorization_ttl_seconds: int = 120):
        self._key = signing_key.encode("utf-8")
        self._ttl = authorization_ttl_seconds

    @staticmethod
    def normalize(identity: AuthenticatedAgent, request: RuntimeActionInput) -> Dict[str, Any]:
        return normalize_action(identity, request)

    @staticmethod
    def digest(normalized: Dict[str, Any]) -> str:
        return compute_action_digest(normalized)

    def evaluate(
        self,
        identity: AuthenticatedAgent,
        request: RuntimeActionInput,
        correlation_id: str,
    ) -> Tuple[StoredAction, RuntimeDecision]:
        normalized = self.normalize(identity, request)
        digest = self.digest(normalized)
        action_id = "act_" + uuid.uuid4().hex
        decision, reason_code, explanation, signals = self._policy(identity, normalized)
        action = StoredAction(
            action_id=action_id,
            identity=identity,
            session_id=request.session_id,
            normalized=normalized,
            digest=digest,
            decision=decision,
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
        )
        token, expires_at = (None, None)
        if decision == "ALLOW":
            token, expires_at = self.issue_authorization(action)

        return action, RuntimeDecision(
            action_id=action_id,
            decision=decision,
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            reason_code=reason_code,
            explanation=explanation,
            risk_signals=signals,
            action_digest=digest,
            correlation_id=correlation_id,
            execution_authorization=token,
            execution_authorization_expires_at=expires_at,
        )

    def _policy(
        self,
        identity: AuthenticatedAgent,
        action: Dict[str, Any],
    ) -> Tuple[str, str, str, List[str]]:
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

    def issue_authorization(self, action: StoredAction) -> Tuple[str, datetime]:
        return issue_execution_token(
            signing_key=self._key,
            action_id=action.action_id,
            identity=action.identity,
            session_id=action.session_id,
            digest=action.digest,
            policy_version=self.policy_version,
            ttl_seconds=self._ttl,
        )

    def verify_authorization(
        self,
        token: str,
        action: StoredAction,
        identity: AuthenticatedAgent,
    ) -> bool:
        return verify_execution_token(
            signing_key=self._key,
            token=token,
            action_id=action.action_id,
            identity=identity,
            session_id=action.session_id,
            digest=action.digest,
            policy_version=self.policy_version,
        )

    @staticmethod
    def execute_safe_echo(action: StoredAction) -> Dict[str, Any]:
        return execute_safe_action(action.decision, action.normalized, action.action_id)
