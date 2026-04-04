"""
WealthTracker 資料庫連線模組

支援 SQLAlchemy 2.0 async engine。
開發模式使用 SQLite，生產環境使用 PostgreSQL（Neon / Railway / Render）。
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_db_url(raw_url: str) -> str:
    """將各種資料庫 URL 格式轉換為 SQLAlchemy async 驅動程式格式。

    支援：
    - postgres://     → postgresql+asyncpg://  (Heroku/Railway/Neon 格式)
    - postgresql://   → postgresql+asyncpg://
    - postgresql+asyncpg:// → 不變
    - sqlite+aiosqlite://   → 不變
    """
    url = raw_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # asyncpg 不支援 URL 中的 sslmode 參數，需將其從連線字串過濾（我們已在 connect_args 啟用 SSL）
    if "?" in url and "sslmode=" in url:
        url = url.split("?")[0]
        
    return url


def _needs_ssl(url: str) -> bool:
    """判斷是否需要 SSL 連線（雲端 PostgreSQL 服務通常需要）"""
    ssl_hosts = ["neon.tech", "supabase.co", "railway.app"]
    return any(host in url for host in ssl_hosts) or "sslmode=require" in url


# 建構資料庫 URL
_db_url = _build_db_url(settings.database_url)

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

    # 雲端 PostgreSQL（如 Neon）需要 SSL 連線
    if _needs_ssl(settings.database_url):
        _engine_kwargs.setdefault("connect_args", {})
        _engine_kwargs["connect_args"]["ssl"] = "require"
        logger.info("已啟用 SSL 連線（偵測到雲端 PostgreSQL）")

logger.info("資料庫引擎: %s", "SQLite" if settings.use_sqlite else "PostgreSQL")

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

