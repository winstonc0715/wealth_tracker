"""
加密貨幣報價提供者

透過 CoinGecko 公開 API 取得加密貨幣即時與歷史價格。
免費方案速率限制：10-50 次/分鐘，需搭配快取使用。
"""

import logging
from datetime import datetime
from decimal import Decimal

import httpx

from app.price.base import (
    PriceProvider, PriceData, HistoricalPrice,
    PriceNotFoundError, ProviderError, SearchResult
)

logger = logging.getLogger(__name__)

# CoinGecko 幣種代碼對應表（常用）
SYMBOL_TO_COINGECKO_ID: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "DOGE": "dogecoin",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "USDT": "tether",
    "USDC": "usd-coin",
}

# 時間範圍對應 CoinGecko 天數
TIMEFRAME_TO_DAYS: dict[str, int] = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "5Y": 1825,
}

BASE_URL = "https://api.coingecko.com/api/v3"


class CryptoProvider(PriceProvider):
    """CoinGecko 加密貨幣報價提供者"""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=10.0,
            headers={"Accept": "application/json"},
        )

    def _get_coin_id(self, symbol: str) -> str:
        """將 symbol 轉換為 CoinGecko coin ID"""
        symbol_upper = symbol.upper()
        coin_id = SYMBOL_TO_COINGECKO_ID.get(symbol_upper)
        if not coin_id:
            # 嘗試直接使用小寫 symbol
            return symbol.lower()
        return coin_id

    async def get_current_price(self, symbol: str) -> PriceData:
        """取得加密貨幣即時報價"""
        coin_id = self._get_coin_id(symbol)
        try:
            response = await self._client.get(
                "/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                },
            )
            response.raise_for_status()
            data = response.json()

            if coin_id not in data:
                raise PriceNotFoundError(f"找不到 {symbol} 的報價")

            coin_data = data[coin_id]
            return PriceData(
                symbol=symbol.upper(),
                price=Decimal(str(coin_data["usd"])),
                currency="USD",
                timestamp=datetime.now(),
                change_pct_24h=Decimal(str(coin_data.get("usd_24h_change", 0))),
                source="coingecko",
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"CoinGecko API 錯誤: {e}") from e

    async def get_historical_prices(
        self, symbol: str, timeframe: str = "1M"
    ) -> list[HistoricalPrice]:
        """取得加密貨幣歷史報價"""
        coin_id = self._get_coin_id(symbol)
        days = TIMEFRAME_TO_DAYS.get(timeframe, 30)

        try:
            response = await self._client.get(
                f"/coins/{coin_id}/ohlc",
                params={"vs_currency": "usd", "days": days},
            )
            response.raise_for_status()
            data = response.json()

            prices = []
            for item in data:
                # CoinGecko OHLC: [timestamp, open, high, low, close]
                ts, o, h, l, c = item
                prices.append(HistoricalPrice(
                    symbol=symbol.upper(),
                    date=datetime.fromtimestamp(ts / 1000),
                    open_price=Decimal(str(o)),
                    high=Decimal(str(h)),
                    low=Decimal(str(l)),
                    close=Decimal(str(c)),
                ))
            return prices
        except httpx.HTTPError as e:
            raise ProviderError(f"CoinGecko 歷史報價錯誤: {e}") from e

    async def validate_symbol(self, symbol: str) -> bool:
        """驗證加密貨幣代碼"""
        try:
            await self.get_current_price(symbol)
            return True
        except (PriceNotFoundError, ProviderError):
            return False

    async def search_symbol(self, query: str) -> list[SearchResult]:
        """搜尋加密貨幣標的"""
        if not query:
            return []
            
        try:
            response = await self._client.get(
                "/search",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for coin in data.get("coins", [])[:10]:
                results.append(SearchResult(
                    symbol=coin.get("symbol", "").upper(),
                    name=coin.get("name", ""),
                    type_box="Crypto",
                    currency="USD"
                ))
            return results
        except Exception as e:
            logger.warning("CoinGecko 搜尋失敗: %s", e)
            return []

    async def close(self):
        """關閉 HTTP Client"""
        await self._client.aclose()
