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
        # 支援 Yahoo 風格代號（ETH-USD、BTC-USDT → ETH、BTC）
        for suffix in ("-USD", "-USDT", "-TWD"):
            if symbol_upper.endswith(suffix):
                symbol_upper = symbol_upper[: -len(suffix)]
                break
        coin_id = SYMBOL_TO_COINGECKO_ID.get(symbol_upper)
        if not coin_id:
            # 嘗試直接使用小寫 symbol
            return symbol_upper.lower()
        return coin_id

    async def get_current_price(self, symbol: str) -> PriceData:
        """取得加密貨幣即時報價。

        主來源 CoinGecko；失敗時退回 yfinance（SYMBOL-USD）——
        CoinGecko 免費 API 對資料中心 IP（如 Render）常有封鎖/限流。
        """
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
        except (httpx.HTTPError, PriceNotFoundError) as e:
            logger.warning("CoinGecko 報價失敗（%s），改用 yfinance: %s", symbol, e)
            return await self._yfinance_fallback(symbol)

    async def _yfinance_fallback(self, symbol: str) -> PriceData:
        """以 yfinance 取得 SYMBOL-USD 的加密貨幣報價"""
        import asyncio

        base = symbol.upper()
        for suffix in ("-USD", "-USDT", "-TWD"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break

        def _fetch() -> PriceData:
            import yfinance as yf
            ticker = yf.Ticker(f"{base}-USD")
            info = ticker.fast_info
            price = info.get("lastPrice") or info.get("last_price")
            if not price or price <= 0:
                raise ProviderError(f"yfinance 無 {base}-USD 報價")
            prev = info.get("previousClose") or info.get("previous_close")
            change = (
                Decimal(str((price - prev) / prev * 100)) if prev else None
            )
            return PriceData(
                symbol=symbol.upper(),
                price=Decimal(str(price)),
                currency="USD",
                timestamp=datetime.now(),
                change_pct_24h=change,
                source="yfinance",
            )

        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, _fetch)
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"yfinance 加密貨幣報價失敗: {e}") from e

    async def get_market_detail(self, symbol: str) -> "MarketDetail":
        """取得加密貨幣市場詳情（含 52W 高低點）"""
        from app.price.base import MarketDetail
        coin_id = self._get_coin_id(symbol)
        try:
            # 同時請求基本資訊和 OHLC 歷史
            import asyncio
            info_task = self._client.get(
                f"/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "false",
                    "developer_data": "false",
                    "sparkline": "false",
                },
            )
            ohlc_task = self._client.get(
                f"/coins/{coin_id}/ohlc",
                params={"vs_currency": "usd", "days": 365},
            )
            info_resp, ohlc_resp = await asyncio.gather(info_task, ohlc_task)
            info_resp.raise_for_status()
            data = info_resp.json()
            md = data.get("market_data", {})

            # 從 OHLC 數據計算 52W 高低點
            week_52_high = None
            week_52_low = None
            try:
                ohlc_resp.raise_for_status()
                ohlc_data = ohlc_resp.json()
                if ohlc_data:
                    highs = [item[2] for item in ohlc_data]  # [ts, open, high, low, close]
                    lows = [item[3] for item in ohlc_data]
                    week_52_high = max(highs) if highs else None
                    week_52_low = min(lows) if lows else None
            except Exception:
                pass  # OHLC 失敗不影響其他數據

            return MarketDetail(
                symbol=symbol.upper(),
                change_pct_24h=md.get("price_change_percentage_24h"),
                change_pct_7d=md.get("price_change_percentage_7d"),
                change_pct_14d=md.get("price_change_percentage_14d"),
                change_pct_30d=md.get("price_change_percentage_30d"),
                change_pct_60d=md.get("price_change_percentage_60d"),
                change_pct_1y=md.get("price_change_percentage_1y"),
                market_cap=md.get("market_cap", {}).get("usd"),
                week_52_high=week_52_high,
                week_52_low=week_52_low,
                currency="USD",
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"CoinGecko 市場詳情錯誤: {e}") from e

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
            logger.warning(
                "CoinGecko 歷史報價失敗（%s），改用 yfinance: %s", symbol, e
            )
            return await self._yfinance_historical(symbol, timeframe)

    async def _yfinance_historical(
        self, symbol: str, timeframe: str
    ) -> list[HistoricalPrice]:
        """以 yfinance 取得 SYMBOL-USD 的加密貨幣歷史報價"""
        import asyncio

        base = symbol.upper()
        for suffix in ("-USD", "-USDT", "-TWD"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        period = {"1M": "1mo", "3M": "3mo", "1Y": "1y", "5Y": "5y"}.get(
            timeframe, "1mo"
        )

        def _fetch() -> list[HistoricalPrice]:
            import yfinance as yf
            df = yf.Ticker(f"{base}-USD").history(period=period)
            if df.empty:
                return []
            return [
                HistoricalPrice(
                    symbol=symbol.upper(),
                    date=idx.to_pydatetime(),
                    open_price=Decimal(str(round(row["Open"], 8))),
                    high=Decimal(str(round(row["High"], 8))),
                    low=Decimal(str(round(row["Low"], 8))),
                    close=Decimal(str(round(row["Close"], 8))),
                )
                for idx, row in df.iterrows()
            ]

        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            logger.warning("yfinance 加密貨幣歷史報價亦失敗: %s", e)
            return []

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
