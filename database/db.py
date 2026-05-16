from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .models import Base
from config import DB_URL

# Katta yuklamalar uchun ulanishlar hovuzini sozlash
engine = create_async_engine(
    DB_URL,
    pool_size=50,
    max_overflow=100,
    pool_timeout=30,
    pool_recycle=1800
)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)