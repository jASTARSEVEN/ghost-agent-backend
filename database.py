import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData
from common.config import settings

DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "testdb")

Base = declarative_base(metadata=MetaData(schema=DATABASE_SCHEMA))

use_ssl = getattr(settings, "DB_SSL", "false").lower() == "true"

connect_args = {}

if use_ssl:
    ssl_context = ssl.create_default_context()
    connect_args = {"ssl": ssl_context}

# Connection pool configuration with validation
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "30"))

if DB_POOL_SIZE + DB_MAX_OVERFLOW > 100:  
    raise ValueError("Total connection pool size exceeds database limit (100)")

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=30,  
    connect_args=connect_args,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Dependency to get DB session
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()  
            raise
