"""lt_common - Database connections."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lt_common.config import settings
from lt_common.database.models import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
