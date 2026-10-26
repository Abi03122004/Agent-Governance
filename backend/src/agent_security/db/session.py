"""Database Session Management and Health Verification."""

import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from agent_security.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_db_engine() -> AsyncEngine:
    """Retrieve or initialize the SQLAlchemy async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        # Ensure async driver is specified
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        if "sqlite" in db_url:
            _engine = create_async_engine(db_url, echo=settings.DEBUG)
        else:
            _engine = create_async_engine(
                db_url,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                echo=settings.DEBUG,
            )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Retrieve or initialize the session maker."""
    global _session_factory
    if _session_factory is None:
        engine = get_db_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables if they do not exist."""
    try:
        from agent_security.db.models import Base
        engine = get_db_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully.")
    except Exception as exc:
        logger.warning(f"Database table initialization notice: {exc}")


async def check_db_health() -> bool:
    """Execute a lightweight probe to verify database readiness."""
    try:
        engine = get_db_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.warning(f"Database readiness check failed: {exc}")
        return False


async def close_db() -> None:
    """Cleanly dispose of database connections upon shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
