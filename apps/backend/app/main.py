"""
WealthTracker FastAPI 應用程式入口

包含 CORS 設定、全域錯誤處理中介軟體、
啟動事件（初始化資料庫與預設資料）。
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, engine
from app.redis_client import close_redis
from app.api.router import api_router
from app.worker import setup_worker, stop_worker

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # === 啟動時 ===
    logger.info("🚀 WealthTracker API 啟動中...")
    logger.info("環境: %s", settings.app_env)

    # 初始化資料庫（開發模式自動建表）
    await init_db()
    logger.info("✅ 資料庫初始化完成")

    # 寫入預設資產類別
    await _seed_default_categories()

    # 啟動背景報價同步器
    setup_worker()

    yield

    # === 關閉時 ===
    logger.info("WealthTracker API 關閉中...")
    stop_worker()
    await close_redis()
    await engine.dispose()
    logger.info("👋 WealthTracker API 已關閉")


async def _seed_default_categories():
    """寫入預設資產類別（若不存在）"""
    from sqlalchemy import select
    from app.database import async_session
    from app.models.asset_category import AssetCategory, DEFAULT_CATEGORIES

    async with async_session() as session:
        # 檢查是否已有資料
        result = await session.execute(select(AssetCategory))
        existing = result.scalars().all()

        if not existing:
            for cat_data in DEFAULT_CATEGORIES:
                session.add(AssetCategory(**cat_data))
            await session.commit()
            logger.info("✅ 預設資產類別已寫入 (%d 筆)", len(DEFAULT_CATEGORIES))
        else:
            logger.info("資產類別已存在 (%d 筆)", len(existing))


# 建立 FastAPI 應用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="跨平台資產管理系統 API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# === 例外攔截中介軟體 ===
# 必須先於 CORSMiddleware 加入（add_middleware 先加者在內側），
# 讓 500 回應也經過 CORS 處理；否則例外會穿透到最外層的
# ServerErrorMiddleware，回應缺 CORS header，瀏覽器只看得到
# 「Failed to fetch」而非真正的錯誤。
async def _catch_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error(
            "%s %s - 500 Error: %s",
            request.method, request.url.path, str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal Server Error",
                # 生產環境不洩漏例外內容
                "detail": str(exc) if settings.is_development else None,
            },
        )

from starlette.middleware.base import BaseHTTPMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=_catch_unhandled_exceptions)

# === CORS 中介軟體 ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 全域錯誤與日誌處理 ===

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """記錄每個請求的處理時間"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        "%s %s - %d (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )

    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全域例外處理器，確保回應帶有 CORS Headers"""
    logger.error(
        "%s %s - 500 Error: %s",
        request.method,
        request.url.path,
        str(exc),
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "detail": str(exc) if settings.is_development else None,
        },
    )

# === 註冊路由 ===
app.include_router(api_router)


# === 健康檢查 ===

@app.get("/health", tags=["系統"])
async def health_check():
    """API 健康檢查"""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.app_env,
    }
