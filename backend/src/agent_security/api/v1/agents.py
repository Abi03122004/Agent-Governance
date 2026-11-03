"""Agents and Credentials API Endpoints."""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.config import get_settings
from agent_security.db.session import get_db
from agent_security.db.models import (
    AgentModel,
    AgentCredentialModel,
    AgentProviderCredentialModel,
    ProjectModel,
    MembershipModel,
    RuntimeActionModel,
    AgentSessionModel,
)
from agent_security.domain.identity import AgentIdentity, AgentCredential, User
from agent_security.services.auth import generate_agent_credential
from agent_security.middleware.auth import get_current_user, get_user_authorized_org_ids
from agent_security.services.audit_service import AuditService
from agent_security.security.vault import encrypt_provider_credential, compute_key_fingerprint

router = APIRouter(prefix="/agents", tags=["Agents"])


async def _verify_agent_org_access(db: AsyncSession, organization_id: str, current_user: User):
    mem_res = await db.execute(
        select(MembershipModel).where(
            MembershipModel.user_id == current_user.id,
            MembershipModel.organization_id == organization_id,
        ).limit(1)
    )
    if not mem_res.scalars().first():
        raise HTTPException(
            status_code=403,
            detail="Forbidden: User is not authorized to access resources in this organization",
        )


class AgentCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    organization_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    environment: str = Field(default="development", min_length=1, max_length=64)
    purpose: Optional[str] = Field(None, max_length=512)
    framework: Optional[str] = Field(default="custom", max_length=64)
    llm_provider: Optional[str] = Field(default="openai", max_length=64)
    default_model: Optional[str] = Field(default="gpt-4o-mini", max_length=128)
    endpoint: Optional[str] = Field(default=None, max_length=512)
    provider_api_key: Optional[str] = Field(default=None, max_length=1024)


class AgentUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(active|revoked|suspended)$")


class CredentialCreate(BaseModel):
    expires_in_seconds: Optional[int] = Field(None, gt=0)


class CredentialResponse(BaseModel):
    id: str
    plaintext_secret: str
    agent_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class ProviderCredentialCreate(BaseModel):
    provider: str = Field(..., min_length=2, max_length=64)
    api_key: str = Field(..., min_length=4, max_length=1024)


class ProviderCredentialResponse(BaseModel):
    agent_id: str
    provider: str
    key_fingerprint: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


def _to_agent_identity(
    a: AgentModel,
    provider_cred: Optional[AgentProviderCredentialModel] = None,
) -> AgentIdentity:
    return AgentIdentity(
        id=a.id,
        organization_id=a.organization_id,
        project_id=a.project_id,
        name=a.name,
        owner=a.owner,
        environment=a.environment,
        purpose=a.purpose,
        framework=getattr(a, "framework", "custom"),
        llm_provider=getattr(a, "llm_provider", "openai"),
        default_model=getattr(a, "default_model", "gpt-4o-mini"),
        endpoint=getattr(a, "endpoint", None),
        connection_status=getattr(a, "connection_status", "registered"),
        last_seen_at=getattr(a, "last_seen_at", None),
        governed_requests_count=getattr(a, "governed_requests_count", 0),
        provider_key_configured=bool(provider_cred and provider_cred.is_active),
        key_fingerprint=provider_cred.key_fingerprint if provider_cred else None,
        status=a.status,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.post("", response_model=AgentIdentity, status_code=201)
async def create_agent(agent: AgentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _verify_agent_org_access(db, agent.organization_id, current_user)
    
    p_res = await db.execute(
        select(ProjectModel).where(
            ProjectModel.id == agent.project_id,
            ProjectModel.organization_id == agent.organization_id,
        )
    )
    if not p_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found or does not belong to organization")
        
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent.id))
    if a_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent ID already exists")
        
    db_agent = AgentModel(
        id=agent.id,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        name=agent.name,
        owner=current_user.email,
        environment=agent.environment,
        purpose=agent.purpose,
        framework=agent.framework or "custom",
        llm_provider=agent.llm_provider or "openai",
        default_model=agent.default_model or "gpt-4o-mini",
        endpoint=agent.endpoint,
        connection_status="registered",
        status="active",
    )
    db.add(db_agent)
    await db.flush()

    active_provider_cred = None
    if agent.provider_api_key and agent.provider_api_key.strip():
        encrypted_val = encrypt_provider_credential(agent.provider_api_key.strip())
        fingerprint = compute_key_fingerprint(agent.provider_api_key.strip())
        active_provider_cred = AgentProviderCredentialModel(
            id=f"pcred_{uuid.uuid4().hex[:12]}",
            organization_id=db_agent.organization_id,
            project_id=db_agent.project_id,
            agent_id=db_agent.id,
            provider=agent.llm_provider or "openai",
            encrypted_api_key=encrypted_val,
            key_fingerprint=fingerprint,
            encryption_key_version=1,
            is_active=True,
        )
        db.add(active_provider_cred)
        await AuditService.record_event(
            db,
            organization_id=db_agent.organization_id,
            project_id=db_agent.project_id,
            agent_id=db_agent.id,
            event_type="agent.provider_credential_configured",
            details={
                "provider": active_provider_cred.provider,
                "key_fingerprint": fingerprint,
            },
        )

    await AuditService.record_event(
        db,
        organization_id=db_agent.organization_id,
        project_id=db_agent.project_id,
        agent_id=db_agent.id,
        event_type="agent.created",
        details={
            "name": db_agent.name,
            "environment": db_agent.environment,
            "framework": db_agent.framework,
            "llm_provider": db_agent.llm_provider,
            "owner": db_agent.owner,
        },
    )
    await db.commit()
    await db.refresh(db_agent)
    
    return _to_agent_identity(db_agent, active_provider_cred)


@router.get("", response_model=List[AgentIdentity])
async def list_agents(organization_id: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if organization_id:
        await _verify_agent_org_access(db, organization_id, current_user)
        stmt = select(AgentModel).where(AgentModel.organization_id == organization_id)
    else:
        user_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not user_org_ids:
            return []
        stmt = select(AgentModel).where(AgentModel.organization_id.in_(user_org_ids))
    result = await db.execute(stmt)
    agents = result.scalars().all()

    # Batch load active provider credentials
    agent_ids = [a.id for a in agents]
    cred_map: Dict[str, AgentProviderCredentialModel] = {}
    if agent_ids:
        p_res = await db.execute(
            select(AgentProviderCredentialModel).where(
                AgentProviderCredentialModel.agent_id.in_(agent_ids),
                AgentProviderCredentialModel.is_active == True,
            )
        )
        for pc in p_res.scalars().all():
            cred_map[pc.agent_id] = pc

    return [_to_agent_identity(a, cred_map.get(a.id)) for a in agents]


@router.get("/{agent_id}", response_model=AgentIdentity)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)
        
    p_res = await db.execute(
        select(AgentProviderCredentialModel).where(
            AgentProviderCredentialModel.agent_id == agent_id,
            AgentProviderCredentialModel.is_active == True,
        ).order_by(AgentProviderCredentialModel.updated_at.desc())
    )
    pc = p_res.scalars().first()

    return _to_agent_identity(a, pc)


@router.patch("/{agent_id}", response_model=AgentIdentity)
async def update_agent_status(agent_id: str, update: AgentUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)
        
    a.status = update.status
    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.status_updated",
        severity="WARN" if update.status in ["suspended", "revoked"] else "INFO",
        details={"status": update.status},
    )
    await db.commit()
    await db.refresh(a)

    p_res = await db.execute(
        select(AgentProviderCredentialModel).where(
            AgentProviderCredentialModel.agent_id == agent_id,
            AgentProviderCredentialModel.is_active == True,
        )
    )
    pc = p_res.scalars().first()
    
    return _to_agent_identity(a, pc)


@router.post("/{agent_id}/credentials", response_model=CredentialResponse, status_code=201)
async def create_credential(
    agent_id: str,
    payload: Optional[CredentialCreate] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)
        
    plain_secret, hashed_secret = generate_agent_credential()
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=payload.expires_in_seconds)) if (payload and payload.expires_in_seconds) else None

    cred = AgentCredentialModel(
        id=f"cred_{uuid.uuid4().hex[:12]}",
        agent_id=a.id,
        secret_hash=hashed_secret,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(cred)
    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.credential_created",
        details={"credential_id": cred.id, "expires_at": str(expires_at)},
    )
    await db.commit()
    await db.refresh(cred)
    
    return CredentialResponse(
        id=cred.id,
        plaintext_secret=plain_secret,
        agent_id=cred.agent_id,
        created_at=cred.created_at,
        expires_at=cred.expires_at,
    )


@router.post("/{agent_id}/credentials/rotate", response_model=CredentialResponse, status_code=201)
async def rotate_credential(
    agent_id: str,
    payload: Optional[CredentialCreate] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    now = datetime.now(timezone.utc)
    active_creds_res = await db.execute(
        select(AgentCredentialModel).where(
            AgentCredentialModel.agent_id == agent_id,
            AgentCredentialModel.is_active == True,
        )
    )
    for c in active_creds_res.scalars().all():
        c.is_active = False
        c.revoked_at = now

    plain_secret, hashed_secret = generate_agent_credential()
    expires_at = (now + timedelta(seconds=payload.expires_in_seconds)) if (payload and payload.expires_in_seconds) else None

    new_cred = AgentCredentialModel(
        id=f"cred_{uuid.uuid4().hex[:12]}",
        agent_id=a.id,
        secret_hash=hashed_secret,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(new_cred)
    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.credential_rotated",
        details={"new_credential_id": new_cred.id, "expires_at": str(expires_at)},
    )
    await db.commit()
    await db.refresh(new_cred)

    return CredentialResponse(
        id=new_cred.id,
        plaintext_secret=plain_secret,
        agent_id=new_cred.agent_id,
        created_at=new_cred.created_at,
        expires_at=new_cred.expires_at,
    )


@router.post("/{agent_id}/credentials/{credential_id}/revoke", response_model=AgentCredential)
async def revoke_credential(agent_id: str, credential_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent_row = a_res.scalar_one_or_none()
    if not agent_row:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, agent_row.organization_id, current_user)

    result = await db.execute(
        select(AgentCredentialModel).where(
            AgentCredentialModel.id == credential_id,
            AgentCredentialModel.agent_id == agent_id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
        
    cred.is_active = False
    cred.revoked_at = datetime.now(timezone.utc)
    await AuditService.record_event(
        db,
        organization_id=agent_row.organization_id,
        project_id=agent_row.project_id,
        agent_id=agent_id,
        event_type="agent.credential_revoked",
        severity="WARN",
        details={"credential_id": cred.id},
    )
    await db.commit()
    await db.refresh(cred)
    
    return AgentCredential(
        id=cred.id,
        agent_id=cred.agent_id,
        is_active=cred.is_active,
        created_at=cred.created_at,
        expires_at=cred.expires_at,
        revoked_at=cred.revoked_at,
    )


# =========================================================================
# PROVIDER CREDENTIAL VAULT ENDPOINTS (AES-256-GCM ENCRYPTED AT REST)
# =========================================================================

@router.post("/{agent_id}/provider-credential", response_model=ProviderCredentialResponse, status_code=201)
async def set_provider_credential(
    agent_id: str,
    payload: ProviderCredentialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store or rotate an upstream LLM provider API key encrypted with AES-256-GCM."""
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = a_res.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    now = datetime.now(timezone.utc)
    # Deactivate existing credentials for this provider on this agent
    existing_res = await db.execute(
        select(AgentProviderCredentialModel).where(
            AgentProviderCredentialModel.agent_id == agent_id,
            AgentProviderCredentialModel.provider == payload.provider.lower(),
            AgentProviderCredentialModel.is_active == True,
        )
    )
    for c in existing_res.scalars().all():
        c.is_active = False
        c.revoked_at = now

    encrypted_key = encrypt_provider_credential(payload.api_key.strip())
    fingerprint = compute_key_fingerprint(payload.api_key.strip())

    cred = AgentProviderCredentialModel(
        id=f"pcred_{uuid.uuid4().hex[:12]}",
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        provider=payload.provider.lower(),
        encrypted_api_key=encrypted_key,
        key_fingerprint=fingerprint,
        encryption_key_version=1,
        is_active=True,
    )
    db.add(cred)
    a.llm_provider = payload.provider.lower()
    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.provider_credential_updated",
        details={
            "provider": cred.provider,
            "key_fingerprint": fingerprint,
        },
    )
    await db.commit()
    await db.refresh(cred)

    return ProviderCredentialResponse(
        agent_id=cred.agent_id,
        provider=cred.provider,
        key_fingerprint=cred.key_fingerprint,
        is_active=cred.is_active,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


@router.get("/{agent_id}/provider-credential", response_model=Optional[ProviderCredentialResponse])
async def get_provider_credential(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve masked metadata for the active provider credential. Never returns secret material."""
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = a_res.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    res = await db.execute(
        select(AgentProviderCredentialModel).where(
            AgentProviderCredentialModel.agent_id == agent_id,
            AgentProviderCredentialModel.is_active == True,
        ).order_by(AgentProviderCredentialModel.updated_at.desc())
    )
    cred = res.scalars().first()
    if not cred:
        return None

    return ProviderCredentialResponse(
        agent_id=cred.agent_id,
        provider=cred.provider,
        key_fingerprint=cred.key_fingerprint,
        is_active=cred.is_active,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


@router.post("/{agent_id}/provider-credential/revoke", status_code=200)
async def revoke_provider_credential(
    agent_id: str,
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke active provider credentials for an agent."""
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = a_res.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    stmt = select(AgentProviderCredentialModel).where(
        AgentProviderCredentialModel.agent_id == agent_id,
        AgentProviderCredentialModel.is_active == True,
    )
    if provider:
        stmt = stmt.where(AgentProviderCredentialModel.provider == provider.lower())
    
    rows = (await db.execute(stmt)).scalars().all()
    now = datetime.now(timezone.utc)
    for c in rows:
        c.is_active = False
        c.revoked_at = now

    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.provider_credential_revoked",
        severity="WARN",
        details={"revoked_count": len(rows), "provider": provider},
    )
    await db.commit()
    return {"status": "revoked", "count": len(rows)}


@router.get("/{agent_id}/integration")
async def get_agent_integration_instructions(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate framework-specific integration instructions for external AI agents."""
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = a_res.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    gateway_url = f"http://127.0.0.1:{get_settings().PORT}"
    proxy_url = f"{gateway_url}/api/v1/proxy/v1"
    
    snippets = {
        "python_openai": f"""from openai import OpenAI

# The external agent holds ONLY its governance bearer token (agt_...)
# The real provider API key resides safely in the gateway vault!
client = OpenAI(
    base_url="{proxy_url}",
    api_key="<YOUR_AGENT_BEARER_TOKEN>"  # agt_...
)

response = client.chat.completions.create(
    model="{a.default_model or 'gpt-4o-mini'}",
    messages=[
        {{"role": "user", "content": "Hello governed world!"}}
    ]
)
print(response.choices[0].message.content)
""",
        "langgraph": f"""# 1. LLM Proxy (Interception of Model Calls)
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="{proxy_url}",
    api_key="<YOUR_AGENT_BEARER_TOKEN>",
    model="{a.default_model or 'gpt-4o-mini'}",
)

# 2. Runtime Tool Action Governance (Interception of Side-Effect Tools)
from governance_sdk.client import GovernanceClient
from governance_sdk.adapters.langgraph import wrap_tools, GovernedLangGraphTool
from langgraph.prebuilt import ToolNode

gov_client = GovernanceClient(
    gateway_url="{gateway_url}",
    api_key="<YOUR_AGENT_BEARER_TOKEN>",
)

# Wrap existing tools for LangGraph StateGraph & ToolNode
governed_tools = wrap_tools(my_tools, client=gov_client)
tool_node = ToolNode(governed_tools)
""",
        "crewai": f"""import os
from crewai import Agent, LLM

governed_llm = LLM(
    model="openai/{a.default_model or 'gpt-4o-mini'}",
    base_url="{proxy_url}",
    api_key="<YOUR_AGENT_BEARER_TOKEN>",
)

researcher = Agent(
    role="Governed Researcher",
    goal="Gather intelligence with audit logging",
    backstory="Autonomous agent bound to enterprise security controls",
    llm=governed_llm,
)
""",
        "autogen": f"""config_list = [
    {{
        "model": "{a.default_model or 'gpt-4o-mini'}",
        "base_url": "{proxy_url}",
        "api_key": "<YOUR_AGENT_BEARER_TOKEN>",
    }}
]
""",
        "openhands": f"""# Runtime Action Governance & LLM Proxy Configuration
# Place in external/OpenHands/.env or container environment:

# 1. LLM Proxy (Model Call Governance)
OPENAI_BASE_URL={proxy_url}
OPENAI_API_KEY=<YOUR_AGENT_BEARER_TOKEN>
LLM_MODEL={a.default_model or 'gpt-4o-mini'}

# 2. Runtime Tool Action Governance (Shell, Filesystem, Browser, MCP)
GOVERNANCE_GATEWAY_URL={gateway_url}
GOVERNANCE_API_KEY=<YOUR_AGENT_BEARER_TOKEN>
""",
    }

    return {
        "agent_id": a.id,
        "framework": a.framework,
        "llm_provider": a.llm_provider,
        "default_model": a.default_model,
        "gateway_url": gateway_url,
        "proxy_base_url": proxy_url,
        "instructions": snippets,
    }


# =========================================================================
# PURGE / DELETION ENDPOINTS
# =========================================================================

@router.delete("/{agent_id}", status_code=200)
async def delete_agent(
    agent_id: str,
    rationale: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete an agent and its credentials. Only accessible by authenticated human operator."""
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    org_id = a.organization_id
    proj_id = a.project_id
    agent_name = a.name

    await db.execute(delete(RuntimeActionModel).where(RuntimeActionModel.agent_id == agent_id))
    await db.execute(delete(AgentSessionModel).where(AgentSessionModel.agent_id == agent_id))
    await db.execute(delete(AgentProviderCredentialModel).where(AgentProviderCredentialModel.agent_id == agent_id))

    await db.delete(a)
    await db.flush()

    await AuditService.record_event(
        db,
        organization_id=org_id,
        project_id=proj_id,
        agent_id=agent_id,
        event_type="agent.deleted_by_human",
        severity="WARN",
        details={
            "agent_id": agent_id,
            "name": agent_name,
            "operator": current_user.email or current_user.id,
            "rationale": rationale or "Human Operator Authorized Purge",
        },
    )
    await db.commit()

    return {"status": "deleted", "agent_id": agent_id, "name": agent_name}


@router.post("/purge-inactive", status_code=200)
async def purge_inactive_agents(
    organization_id: Optional[str] = None,
    rationale: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Purge all suspended or revoked agents within tenant scope. Only accessible by human operator."""
    if organization_id:
        await _verify_agent_org_access(db, organization_id, current_user)
        target_org_ids = [organization_id]
    else:
        target_org_ids = [m.organization_id for m in (await db.execute(select(MembershipModel).where(MembershipModel.user_id == current_user.id))).scalars().all()]

    inactive_agents_res = await db.execute(
        select(AgentModel).where(
            AgentModel.organization_id.in_(target_org_ids),
            AgentModel.status.in_(["suspended", "revoked"]),
        )
    )
    inactive_agents = inactive_agents_res.scalars().all()
    purged_ids = []

    for a in inactive_agents:
        purged_ids.append(a.id)
        await db.execute(delete(RuntimeActionModel).where(RuntimeActionModel.agent_id == a.id))
        await db.execute(delete(AgentSessionModel).where(AgentSessionModel.agent_id == a.id))
        await db.execute(delete(AgentProviderCredentialModel).where(AgentProviderCredentialModel.agent_id == a.id))
        await db.delete(a)

    if purged_ids:
        await db.flush()
        for org_id in target_org_ids:
            await AuditService.record_event(
                db,
                organization_id=org_id,
                event_type="agents.bulk_purged_by_human",
                severity="WARN",
                details={
                    "purged_count": len(purged_ids),
                    "purged_agent_ids": purged_ids,
                    "operator": current_user.email or current_user.id,
                    "rationale": rationale or "Human Operator Purge",
                },
            )
        await db.commit()

    return {"status": "purged", "count": len(purged_ids), "purged_agent_ids": purged_ids}
