"""
WealthTracker 資料庫連線模組

支援 SQLAlchemy 2.0 async engine。
開發模式使用 SQLite，生產環境使用 PostgreSQL。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 根據資料庫類型調整引擎參數
_engine_kwargs: dict = {
    "echo": settings.is_development,
}

if settings.use_sqlite:
    # SQLite 需要特殊的 connect_args，允許跨執行緒存取
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL 連線池設定
    _engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
    })

# 自動轉換資料庫 URL 為非同步驅動程式
_db_url = settings.database_url
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(_db_url, **_engine_kwargs)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 ORM Model 的基礎類別"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依賴注入：取得資料庫 session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """初始化資料庫（開發模式下自動建立所有表）"""
    if settings.use_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
