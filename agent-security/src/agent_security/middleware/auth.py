"""Authentication and Authorization Middleware / Dependencies."""

from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from agent_security.db.session import get_db
from agent_security.db.models import AgentCredentialModel, AgentModel, UserModel, MembershipModel
from agent_security.domain.identity import AgentIdentity, User, Organization
from agent_security.services.auth import hash_secret

security = HTTPBearer()

# For local development, we simulate a logged in human user by reading the "X-User-Email" header.
# In a real environment, this would be an OIDC token validation.
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    email = request.headers.get("X-User-Email")
    if not email:
        raise HTTPException(status_code=401, detail="Missing X-User-Email header for development auth")
    
    result = await db.execute(
        select(UserModel).where(UserModel.email == email, UserModel.status == "active")
    )
    user_record = result.scalar_one_or_none()
    if not user_record:
        raise HTTPException(status_code=401, detail="User not found or inactive")
        
    return User(
        id=user_record.id,
        email=user_record.email,
        display_name=user_record.display_name,
        status=user_record.status,
        created_at=user_record.created_at,
        updated_at=user_record.updated_at
    )

def require_org_role(allowed_roles: list[str]):
    """Returns a dependency that ensures the current user has the required role in the target organization."""
    async def role_checker(organization_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        result = await db.execute(
            select(MembershipModel).where(
                MembershipModel.user_id == current_user.id,
                MembershipModel.organization_id == organization_id
            )
        )
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this organization")
            
        if membership.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Requires one of roles: {allowed_roles}")
            
        return current_user
    return role_checker

async def authenticate_agent(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
) -> AgentIdentity:
    """
    Validates an incoming agent credential and returns the authenticated AgentIdentity.
    Enforces tenant isolation by returning an identity securely bound to an organization and project.
    """
    secret = credentials.credentials
    hashed = hash_secret(secret)
    
    result = await db.execute(
        select(AgentCredentialModel, AgentModel)
        .join(AgentModel, AgentCredentialModel.agent_id == AgentModel.id)
        .where(AgentCredentialModel.secret_hash == hashed)
    )
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid agent credentials")
        
    cred_record, agent = row
    
    if not cred_record.is_active:
        raise HTTPException(status_code=401, detail="Credential is not active")
        
    now = datetime.now(timezone.utc)
    if cred_record.expires_at and cred_record.expires_at < now:
        raise HTTPException(status_code=401, detail="Credential expired")
        
    if cred_record.revoked_at:
        raise HTTPException(status_code=401, detail="Credential revoked")
        
    if agent.status == "revoked":
        raise HTTPException(status_code=401, detail="Agent is revoked")
        
    return AgentIdentity(
        id=agent.id,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        name=agent.name,
        owner=agent.owner,
        environment=agent.environment,
        purpose=agent.purpose,
        status=agent.status,
        created_at=agent.created_at,
        updated_at=agent.updated_at
    )


async def authenticate_agent_async(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> AgentIdentity:
    """Async runtime authentication; identity comes exclusively from the credential."""
    hashed = hash_secret(credentials.credentials)
    result = await db.execute(
        select(AgentCredentialModel, AgentModel)
        .join(AgentModel, AgentCredentialModel.agent_id == AgentModel.id)
        .where(AgentCredentialModel.secret_hash == hashed)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid agent credentials")
    credential, agent = row
    now = datetime.now(timezone.utc)
    if (not credential.is_active or credential.revoked_at or
            (credential.expires_at and credential.expires_at < now) or agent.status == "revoked"):
        raise HTTPException(status_code=401, detail="Agent credential is not authorized")
    return AgentIdentity(
        id=agent.id, organization_id=agent.organization_id, project_id=agent.project_id,
        name=agent.name, owner=agent.owner, environment=agent.environment, purpose=agent.purpose,
        status=agent.status, created_at=agent.created_at, updated_at=agent.updated_at,
    )
