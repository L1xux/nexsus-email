from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()

_engine = None
_async_session_maker = None


def get_engine():
    global _engine
    if _engine is None:
        from app.core.config import get_settings
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_env == "development",
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def get_session_maker():
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_maker


async def get_db() -> AsyncSession:
    async with get_session_maker()() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)