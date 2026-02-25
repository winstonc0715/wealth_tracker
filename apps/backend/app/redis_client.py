"""
WealthTracker Redis 連線模組

支援 Redis 連線池；若 Redis 不可用，自動降級為記憶體快取。
"""

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Redis 客戶端（延遲初始化）
_redis_client = None

# 記憶體快取（Redis 不可用時的備用方案）
_memory_cache: dict[str, tuple[Any, float]] = {}


async def get_redis():
    """取得 Redis 連線，若不可用則返回 None"""
    global _redis_client

    if settings.redis_url is None:
        return None

    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
            # 測試連線
            await _redis_client.ping()
            logger.info("Redis 連線成功: %s", settings.redis_url)
        except Exception as e:
            logger.warning("Redis 連線失敗，改用記憶體快取: %s", e)
            _redis_client = None
            return None

    return _redis_client


async def cache_get(key: str) -> Any | None:
    """從快取讀取資料，優先 Redis，備用記憶體快取"""
    import time

    redis = await get_redis()
    if redis:
        try:
            value = await redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning("Redis GET 失敗: %s", e)

    # 記憶體快取 fallback
    if key in _memory_cache:
        value, expire_at = _memory_cache[key]
        if time.time() < expire_at:
            return value
        else:
            del _memory_cache[key]

    return None


async def cache_get_stale(key: str) -> Any | None:
    """
    從快取讀取資料（即使已過期也回傳）

    當 API 失敗時，回傳上次成功的報價比回傳 $0 更合理。
    """
    import time

    redis = await get_redis()
    if redis:
        try:
            value = await redis.get(key)
            if value:
                return json.loads(value)
        except Exception:
            pass

    # 記憶體快取（不檢查過期）
    if key in _memory_cache:
        value, _expire_at = _memory_cache[key]
        return value

    return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """寫入快取，優先 Redis，備用記憶體快取"""
    import time

    if ttl is None:
        ttl = settings.price_cache_ttl

    redis = await get_redis()
    if redis:
        try:
            await redis.set(key, json.dumps(value, default=str), ex=ttl)
            return
        except Exception as e:
            logger.warning("Redis SET 失敗: %s", e)

    # 記憶體快取 fallback
    _memory_cache[key] = (value, time.time() + ttl)


async def cache_delete(key: str) -> None:
    """刪除快取"""
    redis = await get_redis()
    if redis:
        try:
            await redis.delete(key)
        except Exception:
            pass

    _memory_cache.pop(key, None)


async def close_redis() -> None:
    """關閉 Redis 連線"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
