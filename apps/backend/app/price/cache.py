"""
報價快取模組

封裝 Redis/記憶體快取邏輯，提供 TTL 控制。
"""

import json
import logging
from decimal import Decimal

from app.price.base import PriceData
from app.redis_client import cache_get, cache_set, cache_get_stale

logger = logging.getLogger(__name__)

# 快取 Key 前綴
CACHE_PREFIX = "price"


def _make_key(provider: str, symbol: str) -> str:
    """產生快取 Key"""
    return f"{CACHE_PREFIX}:{provider}:{symbol.upper()}"


def _price_to_dict(price: PriceData) -> dict:
    """將 PriceData 轉為可序列化的 dict"""
    return {
        "symbol": price.symbol,
        "price": str(price.price),
        "currency": price.currency,
        "timestamp": price.timestamp.isoformat(),
        "change_24h": str(price.change_24h) if price.change_24h else None,
        "change_pct_24h": str(price.change_pct_24h) if price.change_pct_24h else None,
        "source": price.source,
    }


def _dict_to_price(data: dict) -> PriceData:
    """從 dict 還原 PriceData"""
    from datetime import datetime
    return PriceData(
        symbol=data["symbol"],
        price=Decimal(data["price"]),
        currency=data["currency"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
        change_24h=Decimal(data["change_24h"]) if data.get("change_24h") else None,
        change_pct_24h=Decimal(data["change_pct_24h"]) if data.get("change_pct_24h") else None,
        source=data.get("source", "cache"),
    )


async def get_cached_price(
    provider: str, symbol: str
) -> PriceData | None:
    """從快取取得報價"""
    key = _make_key(provider, symbol)
    data = await cache_get(key)
    if data:
        logger.debug("快取命中: %s", key)
        return _dict_to_price(data)
    return None


async def set_cached_price(
    provider: str, symbol: str, price: PriceData, ttl: int | None = None
) -> None:
    """將報價寫入快取"""
    key = _make_key(provider, symbol)
    await cache_set(key, _price_to_dict(price), ttl=ttl)
    logger.debug("快取寫入: %s (TTL=%s)", key, ttl)


async def get_stale_cached_price(
    provider: str, symbol: str
) -> PriceData | None:
    """從快取取得報價（即使已過期），用於 API 失敗時的 fallback"""
    key = _make_key(provider, symbol)
    data = await cache_get_stale(key)
    if data:
        logger.debug("stale 快取命中: %s", key)
        return _dict_to_price(data)
    return None
