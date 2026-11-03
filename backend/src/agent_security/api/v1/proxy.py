"""OpenAI-Compatible LLM Reverse Governance Proxy Endpoint."""

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.config import get_settings
from agent_security.core.hashing import canonical_json_bytes
from agent_security.db.session import get_db
from agent_security.db.models import (
    AgentModel,
    AgentProviderCredentialModel,
    ApprovalRequestModel,
    ExecutionAuthorizationModel,
    LLMPendingRequestModel,
    OrganizationModel,
    ProjectModel,
)
from agent_security.domain.identity import AgentIdentity
from agent_security.middleware.auth import authenticate_agent_async
from agent_security.security.vault import decrypt_provider_credential
from agent_security.security.injection_defense import InjectionDetector
from agent_security.services.audit_service import AuditService
from agent_security.services.anomaly_monitoring import AnomalyMonitoringService
from agent_security.services.realtime import ws_manager
from agent_security.services.provider_adapters import get_provider_adapter, ProviderExecutionError

router = APIRouter(prefix="/proxy", tags=["LLM Governance Proxy"])


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stream: Optional[bool] = False
    stop: Optional[Any] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    execution_authorization: Optional[str] = None
    approval_ticket_id: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class ResumeCompletionRequest(BaseModel):
    approval_ticket_id: str
    execution_authorization: str


def _format_openai_error(
    message: str,
    error_type: str = "governance_policy_violation",
    code: str = "POLICY_BLOCKED",
    status_code: int = 403,
    extra: Optional[Dict[str, Any]] = None,
):
    error_dict = {
        "message": message,
        "type": error_type,
        "param": None,
        "code": code,
        **(extra or {}),
    }
    return HTTPException(status_code=status_code, detail={"error": error_dict})


async def _execute_upstream_call(
    db: AsyncSession,
    agent: AgentIdentity,
    model: str,
    messages: List[Dict[str, Any]],
    parameters: Dict[str, Any],
    request_digest: str,
) -> Dict[str, Any]:
    """Retrieve credential, execute upstream LLM call via adapter, and record audit event."""
    cred_res = await db.execute(
        select(AgentProviderCredentialModel).where(
            AgentProviderCredentialModel.agent_id == agent.id,
            AgentProviderCredentialModel.is_active == True,
        ).order_by(AgentProviderCredentialModel.updated_at.desc())
    )
    provider_cred = cred_res.scalars().first()

    if not provider_cred:
        org_cred_res = await db.execute(
            select(AgentProviderCredentialModel).where(
                AgentProviderCredentialModel.organization_id == agent.organization_id,
                AgentProviderCredentialModel.is_active == True,
            ).order_by(AgentProviderCredentialModel.updated_at.desc())
        )
        provider_cred = org_cred_res.scalars().first()

    if not provider_cred:
        raise _format_openai_error(
            "No upstream LLM provider credentials configured for this agent in the secure vault. "
            "Configure an API key in the agent settings or registration modal.",
            error_type="missing_provider_credential",
            code="NO_PROVIDER_CREDENTIAL",
            status_code=400,
        )

    try:
        decrypted_key = decrypt_provider_credential(provider_cred.encrypted_api_key)
    except Exception as exc:
        raise _format_openai_error("Provider credential vault decryption failed", error_type="vault_error", code="VAULT_DECRYPTION_ERROR", status_code=500) from exc

    provider_name = provider_cred.provider
    adapter = get_provider_adapter(provider_name)
    start_time = time.time()

    try:
        provider_response = await adapter.execute(
            model=model,
            messages=messages,
            provider_api_key=decrypted_key,
            parameters=parameters,
        )
    except ProviderExecutionError as p_err:
        await AuditService.record_event(
            db,
            organization_id=agent.organization_id,
            project_id=agent.project_id,
            agent_id=agent.id,
            event_type="llm.provider_error",
            tool_name="llm_proxy",
            canonical_action_hash=request_digest,
            policy_decision="ALLOW",
            execution_state="FAILED",
            severity="ERROR",
            details={
                "model": model,
                "provider": provider_name,
                "error": str(p_err),
                "status_code": p_err.status_code,
            },
        )
        await db.commit()
        raise _format_openai_error(
            f"Upstream provider error: {str(p_err)}",
            error_type="upstream_provider_error",
            code="PROVIDER_ERROR",
            status_code=p_err.status_code,
        ) from p_err
    finally:
        del decrypted_key

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Output inspection
    first_choice_content = ""
    try:
        first_choice_content = provider_response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        pass

    out_wrapper = InjectionDetector.wrap_untrusted_output(first_choice_content, source_tool="llm_proxy")

    # Audit logging
    await AuditService.record_event(
        db,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        event_type="llm.completion_executed",
        tool_name="llm_proxy",
        canonical_action_hash=request_digest,
        policy_decision="ALLOW",
        execution_state="EXECUTED",
        severity="INFO",
        details={
            "model": model,
            "provider": provider_name,
            "latency_ms": elapsed_ms,
            "usage": provider_response.get("usage", {}),
            "threat_detected": out_wrapper.threat_scan.threat_detected,
        },
    )

    # Telemetry update
    await db.execute(
        update(AgentModel)
        .where(AgentModel.id == agent.id)
        .values(
            last_seen_at=datetime.now(timezone.utc),
            connection_status="active",
            governed_requests_count=AgentModel.governed_requests_count + 1,
        )
    )
    await db.commit()

    # Real-time dashboard broadcast
    await ws_manager.broadcast({
        "type": "LLM_REQUEST_EXECUTED",
        "agent_id": agent.id,
        "organization_id": agent.organization_id,
        "model": model,
        "provider": provider_name,
        "tokens": provider_response.get("usage", {}).get("total_tokens", 0),
        "latency_ms": elapsed_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return provider_response


async def _handle_chat_completion(
    req: Request,
    request: ChatCompletionRequest,
    db: AsyncSession,
    agent: AgentIdentity,
):
    if agent.status == "suspended":
        raise _format_openai_error("Agent is suspended; LLM proxy execution prohibited", code="AGENT_SUSPENDED", status_code=403)
    if agent.status != "active":
        raise _format_openai_error("Agent is inactive; LLM proxy execution prohibited", code="AGENT_INACTIVE", status_code=403)

    org_res = await db.execute(select(OrganizationModel).where(OrganizationModel.id == agent.organization_id))
    org_rec = org_res.scalar_one_or_none()
    if org_rec and org_rec.status == "suspended":
        raise _format_openai_error("Organization is suspended", code="TENANT_SUSPENDED", status_code=403)

    proj_res = await db.execute(select(ProjectModel).where(ProjectModel.id == agent.project_id))
    proj_rec = proj_res.scalar_one_or_none()
    if proj_rec and proj_rec.status == "suspended":
        raise _format_openai_error("Project is suspended", code="PROJECT_SUSPENDED", status_code=403)

    raw_dict = await req.json()
    request_digest = hashlib.sha256(canonical_json_bytes(raw_dict)).hexdigest()

    # Check if this request is presenting an approved execution authorization token
    exec_auth_token = req.headers.get("X-Execution-Authorization") or request.execution_authorization
    if exec_auth_token:
        now = datetime.now(timezone.utc)
        token_hash = hashlib.sha256(exec_auth_token.encode()).hexdigest()
        
        # Verify single-use token claim
        claim_stmt = (
            update(ExecutionAuthorizationModel)
            .where(
                ExecutionAuthorizationModel.token_hash == token_hash,
                ExecutionAuthorizationModel.used_at.is_(None),
                ExecutionAuthorizationModel.expires_at > now,
            )
            .values(used_at=now)
        )
        claim_res = await db.execute(claim_stmt)
        if claim_res.rowcount == 0:
            raise _format_openai_error("Invalid, expired, or already-used execution authorization token.", code="INVALID_EXECUTION_TOKEN", status_code=403)
        await db.commit()

        # Token claimed successfully: proceed directly to execution
        parameters = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }
        parameters = {k: v for k, v in parameters.items() if v is not None}
        return await _execute_upstream_call(db, agent, request.model, request.messages, parameters, request_digest)

    # Prompt inspection for threat and policy classification
    extracted_text_parts = []
    for msg in request.messages:
        c = msg.get("content", "")
        if isinstance(c, str):
            extracted_text_parts.append(c)
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "text":
                    extracted_text_parts.append(part.get("text", ""))
    full_prompt_text = " \n ".join(extracted_text_parts)

    threat_scan = InjectionDetector.scan(full_prompt_text)
    if threat_scan.threat_detected:
        await AnomalyMonitoringService.record_injection_threat(
            agent_id=agent.id,
            source_tool="llm_proxy",
            scan_result_dict={
                "risk_score": threat_scan.risk_score,
                "categories": [cat.value for cat in threat_scan.categories],
                "matched_patterns": threat_scan.matched_patterns,
            },
        )

    decision = "ALLOW"
    reason_code = "LLM_REQUEST_PERMITTED"
    explanation = "The LLM request complies with active runtime security policies."

    if threat_scan.risk_score >= 0.8:
        decision = "BLOCK"
        reason_code = "PROMPT_INJECTION_DETECTED"
        explanation = f"Critical prompt injection patterns detected in LLM payload: {', '.join(threat_scan.matched_patterns[:3])}."
    elif any(kw in full_prompt_text.lower() for kw in ["drop database", "rm -rf /", "exfiltrate secrets", "export all keys"]):
        decision = "BLOCK"
        reason_code = "MALICIOUS_PROMPT_PATTERN"
        explanation = "The prompt contains prohibited destructive or exfiltration patterns."
    elif "deploy production" in full_prompt_text.lower() or "migrate database" in full_prompt_text.lower():
        decision = "REQUIRE_APPROVAL"
        reason_code = "HIGH_RISK_ACTION_APPROVAL_REQUIRED"
        explanation = "Production deployment and database migration intents require human operator authorization."

    # CASE A: BLOCK
    if decision == "BLOCK":
        await AuditService.record_event(
            db,
            organization_id=agent.organization_id,
            project_id=agent.project_id,
            agent_id=agent.id,
            event_type="llm.request_blocked",
            tool_name="llm_proxy",
            canonical_action_hash=request_digest,
            policy_decision="BLOCK",
            execution_state="BLOCKED",
            severity="WARN",
            details={
                "model": request.model,
                "reason_code": reason_code,
                "explanation": explanation,
                "risk_score": threat_scan.risk_score,
            },
        )
        await db.commit()
        raise _format_openai_error(f"Governance policy BLOCKED LLM request: {explanation}", code=reason_code, status_code=403)

    # CASE B: REQUIRE_APPROVAL
    if decision == "REQUIRE_APPROVAL":
        ticket_id = f"appr_{uuid.uuid4().hex}"
        pending_id = f"llm_req_{uuid.uuid4().hex}"
        ticket_ttl = get_settings().APPROVAL_TICKET_TTL_SECONDS
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ticket_ttl)

        ticket = ApprovalRequestModel(
            ticket_id=ticket_id,
            organization_id=agent.organization_id,
            action_id=pending_id,
            canonical_action_hash=request_digest,
            status="PENDING",
            expires_at=expires_at,
        )
        db.add(ticket)

        pending_record = LLMPendingRequestModel(
            id=pending_id,
            organization_id=agent.organization_id,
            project_id=agent.project_id,
            agent_id=agent.id,
            approval_ticket_id=ticket_id,
            request_digest=request_digest,
            provider="openai",
            model=request.model,
            request_payload=raw_dict,
            status="PENDING_APPROVAL",
            reason_code=reason_code,
            explanation=explanation,
            expires_at=expires_at,
        )
        db.add(pending_record)

        await AuditService.record_event(
            db,
            organization_id=agent.organization_id,
            project_id=agent.project_id,
            agent_id=agent.id,
            event_type="llm.approval_required",
            tool_name="llm_proxy",
            canonical_action_hash=request_digest,
            policy_decision="REQUIRE_APPROVAL",
            execution_state="AWAITING_APPROVAL",
            severity="INFO",
            details={
                "model": request.model,
                "ticket_id": ticket_id,
                "pending_id": pending_id,
                "reason_code": reason_code,
            },
        )
        await db.commit()

        raise _format_openai_error(
            "LLM request paused: requires human operator authorization before upstream execution.",
            error_type="approval_required",
            code="REQUIRE_APPROVAL",
            status_code=403,
            extra={"approval_ticket_id": ticket_id, "pending_request_id": pending_id},
        )

    # CASE C: ALLOW
    parameters = {
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "top_p": request.top_p,
    }
    parameters = {k: v for k, v in parameters.items() if v is not None}
    return await _execute_upstream_call(db, agent, request.model, request.messages, parameters, request_digest)


@router.post("/chat/completions")
@router.post("/v1/chat/completions")
async def chat_completions(
    req: Request,
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    return await _handle_chat_completion(req, request, db, agent)


@router.post("/chat/completions/resume")
@router.post("/v1/chat/completions/resume")
async def resume_approved_chat_completion(
    req: ResumeCompletionRequest,
    db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    """Resume and execute a previously paused LLM request using its single-use authorization token."""
    now = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(req.execution_authorization.encode()).hexdigest()

    claim_stmt = (
        update(ExecutionAuthorizationModel)
        .where(
            ExecutionAuthorizationModel.token_hash == token_hash,
            ExecutionAuthorizationModel.used_at.is_(None),
            ExecutionAuthorizationModel.expires_at > now,
        )
        .values(used_at=now)
    )
    claim_res = await db.execute(claim_stmt)
    if claim_res.rowcount == 0:
        raise _format_openai_error("Invalid, expired, or already-used execution authorization token.", code="INVALID_EXECUTION_TOKEN", status_code=403)

    auth_rec = (await db.execute(select(ExecutionAuthorizationModel).where(ExecutionAuthorizationModel.token_hash == token_hash))).scalar_one_or_none()
    if not auth_rec:
        raise _format_openai_error("Execution authorization record missing.", code="NOT_FOUND", status_code=404)

    llm_pending = (await db.execute(select(LLMPendingRequestModel).where(LLMPendingRequestModel.id == auth_rec.action_id))).scalar_one_or_none()
    if not llm_pending or llm_pending.agent_id != agent.id or llm_pending.organization_id != agent.organization_id:
        raise _format_openai_error("Pending request record not found or tenant boundary violated.", code="FORBIDDEN", status_code=403)

    saved_payload = llm_pending.request_payload
    model = saved_payload.get("model", "gpt-4o-mini")
    messages = saved_payload.get("messages", [])
    parameters = {
        "temperature": saved_payload.get("temperature"),
        "max_tokens": saved_payload.get("max_tokens"),
        "top_p": saved_payload.get("top_p"),
    }
    parameters = {k: v for k, v in parameters.items() if v is not None}

    result = await _execute_upstream_call(db, agent, model, messages, parameters, llm_pending.request_digest)
    llm_pending.status = "EXECUTED"
    await db.commit()
    return result


@router.get("/models")
@router.get("/v1/models")
async def list_models(
    db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent.id))
    a = a_res.scalar_one_or_none()
    default_model = a.default_model if a and a.default_model else "gpt-4o-mini"

    models = [
        {"id": default_model, "object": "model", "created": 1700000000, "owned_by": "governance-gateway"},
        {"id": "gpt-4o", "object": "model", "created": 1700000000, "owned_by": "openai"},
        {"id": "gpt-4o-mini", "object": "model", "created": 1700000000, "owned_by": "openai"},
        {"id": "gemini-2.5-flash", "object": "model", "created": 1700000000, "owned_by": "google"},
        {"id": "claude-3-5-sonnet", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
    ]
    return {"object": "list", "data": models}
