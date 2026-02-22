"""
報價管理器

統一入口，根據資產類別自動路由到對應的 PriceProvider。
整合快取邏輯：先查快取，過期才呼叫 Provider 取得最新報價。
"""

import asyncio
import logging
from decimal import Decimal

from app.config import get_settings
from app.price.base import PriceData, HistoricalPrice, PriceNotFoundError, SearchResult
from app.price.cache import get_cached_price, set_cached_price
from app.price.crypto import CryptoProvider
from app.price.us_stock import USStockProvider
from app.price.tw_stock import TWStockProvider

logger = logging.getLogger(__name__)

# 資產類別 slug 對應 provider 名稱
CATEGORY_PROVIDER_MAP: dict[str, str] = {
    "crypto": "crypto",
    "us_stock": "us_stock",
    "tw_stock": "tw_stock",
    "fiat": "fiat",
    "liability": "liability",
}


class PriceManager:
    """
    報價管理器

    使用方式：
        manager = PriceManager()
        price = await manager.get_price("BTC", "crypto")
    """

    def __init__(self):
        settings = get_settings()
        self._providers = {
            "crypto": CryptoProvider(api_key=settings.coingecko_api_key),
            "us_stock": USStockProvider(),
            "tw_stock": TWStockProvider(),
        }
        self._ttl = settings.price_cache_ttl
        self._fetching: dict[str, asyncio.Future] = {}

    async def get_price(
        self, symbol: str, category_slug: str, force_refresh: bool = False
    ) -> PriceData:
        """
        取得即時報價（含快取邏輯）

        流程：
        1. 先查快取
        2. 快取過期 → 呼叫對應 Provider
        3. 取得新報價後寫入快取

        Args:
            symbol: 標的代碼
            category_slug: 資產類別 slug
            force_refresh: 是否強制重新取得報價，繞過快取

        Returns:
            PriceData
        """
        provider_name = CATEGORY_PROVIDER_MAP.get(category_slug, "")

        # 法幣和負債不需要報價（或回傳面額 1）
        if category_slug in ("fiat", "liability"):
            return PriceData(
                symbol=symbol,
                price=Decimal("1"),
                currency="TWD",
                source="static",
            )

        provider = self._providers.get(provider_name)
        if not provider:
            raise PriceNotFoundError(
                f"找不到類別 {category_slug} 的報價提供者"
            )

        # 1. 先查快取 (如果非強制更新)
        if not force_refresh:
            cached = await get_cached_price(provider_name, symbol)
            if cached:
                return cached

        # Singleflight: 防範快取擊穿
        # 如果已經有相同的報價請求在進行中，直接等待該請求結果
        flight_key = f"{provider_name}:{symbol}"
        if flight_key in self._fetching:
            logger.info("等待進行中的報價請求: %s (%s)", symbol, category_slug)
            return await self._fetching[flight_key]

        future = asyncio.Future()
        self._fetching[flight_key] = future

        try:
            # 2. 快取未命中，呼叫 Provider
            logger.info("快取未命中，正在取得 %s (%s) 報價...", symbol, category_slug)
            price = await provider.get_current_price(symbol)

            # 3. 寫入快取
            await set_cached_price(provider_name, symbol, price, ttl=self._ttl)
            future.set_result(price)
            return price
        except Exception as e:
            future.set_exception(e)
            raise e
        finally:
            self._fetching.pop(flight_key, None)

    async def get_historical(
        self, symbol: str, category_slug: str, timeframe: str = "1M"
    ) -> list[HistoricalPrice]:
        """取得歷史報價"""
        provider_name = CATEGORY_PROVIDER_MAP.get(category_slug, "")
        provider = self._providers.get(provider_name)

        if not provider:
            return []

        return await provider.get_historical_prices(symbol, timeframe)

    async def get_prices_batch(
        self, items: list[tuple[str, str]], force_refresh: bool = False
    ) -> dict[str, PriceData]:
        """
        批次取得報價

        Args:
            items: [(symbol, category_slug), ...] 列表

        Returns:
            {symbol: PriceData, ...}
        """
        results: dict[str, PriceData] = {}
        for symbol, category_slug in items:
            try:
                results[symbol] = await self.get_price(symbol, category_slug, force_refresh=force_refresh)
            except Exception as e:
                logger.warning("取得 %s 報價失敗: %s", symbol, e)
                
                # 若報價失敗，試圖從快取撈舊資料當 Fallback
                provider_name = CATEGORY_PROVIDER_MAP.get(category_slug, "")
                if provider_name:
                    cached = await get_cached_price(provider_name, symbol)
                    if cached:
                        results[symbol] = cached
                        continue

                # 真沒快取才回傳 0
                results[symbol] = PriceData(
                    symbol=symbol,
                    price=Decimal("0"),
                    currency="USD" if category_slug in ("crypto", "us_stock") else "TWD",
                    source="error",
                )
            
            # API 請求間加入短暫延遲，防範 Rate Limit (429) 
            await asyncio.sleep(0.5)

        return results

    async def search_symbol(self, query: str, category_slug: str) -> list[SearchResult]:
        """
        搜尋標的
        
        Args:
            query: 搜尋關鍵字
            category_slug: 資產類別
            
        Returns:
            SearchResult 列表
        """
        provider_name = CATEGORY_PROVIDER_MAP.get(category_slug, "")
        provider = self._providers.get(provider_name)

        if not provider:
            return []

        if hasattr(provider, "search_symbol"):
            return await provider.search_symbol(query)
            
        return []

    async def close(self):
        """關閉所有 Provider 的資源"""
        for provider in self._providers.values():
            if hasattr(provider, "close"):
                await provider.close()
