"""Authentication and Authorization Middleware / Dependencies."""

from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from agent_security.config import get_settings
from agent_security.db.session import get_db
from agent_security.db.models import AgentCredentialModel, AgentModel, UserModel, MembershipModel
from agent_security.domain.identity import AgentIdentity, User, Organization
from agent_security.services.auth import hash_secret
from agent_security.security.authentication import verify_user_token

security = HTTPBearer()


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Resolve authenticated human user.
    
    In production, strictly requires a cryptographically validated Bearer JWT token.
    Untrusted headers (X-User-Email) cannot impersonate users.
    Development header authentication is permitted ONLY when explicitly configured
    via ALLOW_DEV_HEADER_AUTH outside production.
    """
    settings = get_settings()
    auth_header = request.headers.get("Authorization")

    # 1. Bearer Token Authentication (production standard & OIDC/JWT compatible)
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        payload = verify_user_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired authentication token")

        user_id = payload.get("sub")
        email = payload.get("email")
        stmt = select(UserModel).where(
            (UserModel.id == user_id) | (UserModel.email == email),
            UserModel.status == "active",
        )
        result = await db.execute(stmt)
        user_record = result.scalar_one_or_none()
        if not user_record:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        return User(
            id=user_record.id,
            email=user_record.email,
            display_name=user_record.display_name,
            status=user_record.status,
            created_at=user_record.created_at,
            updated_at=user_record.updated_at,
        )

    # 2. Development Header Authentication (explicit, secure development configuration only)
    if settings.ENVIRONMENT != "production" and settings.ALLOW_DEV_HEADER_AUTH:
        email = request.headers.get("X-User-Email")
        if not email:
            raise HTTPException(
                status_code=401,
                detail="Missing authentication credentials or X-User-Email header",
            )
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
            updated_at=user_record.updated_at,
        )

    # 3. Reject unauthenticated requests in production or when dev auth is disabled
    raise HTTPException(
        status_code=401,
        detail="Authentication credentials required. In production, validated Bearer token is required.",
    )


async def get_user_authorized_org_ids(db: AsyncSession, user_id: str) -> list[str]:
    """Retrieve all organization IDs where the user has active membership."""
    result = await db.execute(
        select(MembershipModel.organization_id).where(MembershipModel.user_id == user_id)
    )
    return [r[0] for r in result.all()]


async def verify_user_org_membership(db: AsyncSession, user_id: str, organization_id: str) -> None:
    """Verify that a user is an active member of the specified organization."""
    result = await db.execute(
        select(MembershipModel).where(
            MembershipModel.user_id == user_id,
            MembershipModel.organization_id == organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail="Forbidden: User is not authorized to access resources in this organization",
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

def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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
    now = datetime.now(timezone.utc)
    exp = _to_utc(cred_record.expires_at)
    if (
        not cred_record.is_active
        or cred_record.revoked_at
        or (exp and exp < now)
        or agent.status == "revoked"
    ):
        raise HTTPException(status_code=401, detail="Invalid agent credentials")
        
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
    exp = _to_utc(credential.expires_at)
    if (not credential.is_active or credential.revoked_at or
            (exp and exp < now) or agent.status == "revoked"):
        raise HTTPException(status_code=401, detail="Invalid agent credentials")
    return AgentIdentity(
        id=agent.id, organization_id=agent.organization_id, project_id=agent.project_id,
        name=agent.name, owner=agent.owner, environment=agent.environment, purpose=agent.purpose,
        status=agent.status, created_at=agent.created_at, updated_at=agent.updated_at,
    )
