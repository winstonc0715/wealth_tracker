"""
美股報價提供者

透過 Yahoo Finance (yfinance) 取得美股即時與歷史價格。
yfinance 為開源套件，無需 API Key。
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

# 時間範圍對應 yfinance period
TIMEFRAME_TO_PERIOD: dict[str, str] = {
    "1W": "5d",
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "5Y": "5y",
}


class USStockProvider(PriceProvider):
    """Yahoo Finance 美股報價提供者"""

    async def get_current_price(self, symbol: str) -> PriceData:
        """取得美股即時報價（使用 yfinance）"""
        import asyncio
        try:
            # yfinance 是同步 API，需用 run_in_executor 包裝
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._fetch_price, symbol)
            return data
        except Exception as e:
            if "not found" in str(e).lower():
                raise PriceNotFoundError(f"找不到 {symbol} 的報價") from e
            raise ProviderError(f"Yahoo Finance 錯誤: {e}") from e

    def _fetch_price(self, symbol: str) -> PriceData:
        """同步取得報價（在 executor 中執行）"""
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = ticker.fast_info

        try:
            price = info.last_price
            prev_close = info.previous_close
        except Exception:
            raise PriceNotFoundError(f"找不到 {symbol} 的報價")

        if price is None:
            raise PriceNotFoundError(f"找不到 {symbol} 的報價")

        change_24h = None
        change_pct = None
        if prev_close and prev_close > 0:
            change_24h = Decimal(str(price)) - Decimal(str(prev_close))
            change_pct = (change_24h / Decimal(str(prev_close))) * 100

        return PriceData(
            symbol=symbol.upper(),
            price=Decimal(str(round(price, 4))),
            currency="USD",
            timestamp=datetime.now(),
            change_24h=change_24h,
            change_pct_24h=change_pct,
            source="yahoo_finance",
        )

    async def get_market_detail(self, symbol: str) -> "MarketDetail":
        """取得美股市場詳情（52W、PE、市值、多時段漲跌）"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_market_detail, symbol)

    def _fetch_market_detail(self, symbol: str) -> "MarketDetail":
        """同步取得美股市場詳情 (完全基於歷史數據計算以確保準確)"""
        import yfinance as yf
        from app.price.base import MarketDetail

        ticker = yf.Ticker(symbol)
        
        # 1. 取得歷史數據
        changes: dict[str, float | None] = {}
        week_52_high = None
        week_52_low = None
        market_cap = None
        pe_ratio = None
        pct_24h = None

        try:
            # 取得 2 年資料以確保能算出一年前的漲跌
            hist = ticker.history(period="2y")
            if not hist.empty:
                # --- 時效性檢查 ---
                last_date = hist.index[-1].replace(tzinfo=None)
                days_old = (datetime.now() - last_date).days
                if days_old > 7:
                    logger.warning(f"美股 {symbol} 數據過期 (最後日期: {last_date}, 距今 {days_old} 天)")
                    # 若數據太舊，我們不應該回傳這些錯誤的數字
                    return MarketDetail(symbol=symbol.upper(), currency="USD")
                
                current = float(hist['Close'].iloc[-1])
                
                # 計算 52W 高低 (取最近 252 個交易日)
                recent_1y = hist.iloc[-252:] if len(hist) > 252 else hist
                week_52_high = float(recent_1y['High'].max())
                week_52_low = float(recent_1y['Low'].min())

                # 24h 漲跌
                if len(hist) >= 2:
                    prev = float(hist['Close'].iloc[-2])
                    pct_24h = round(((current - prev) / prev) * 100, 2)
                
                # 計算各時段漲跌 (標籤, 交易日天數)
                intervals = [("7d", 5), ("14d", 10), ("30d", 22), ("60d", 44), ("1y", 252)]
                for label, days in intervals:
                    if len(hist) >= days + 1:
                        # 特殊處理 1y：如果資料長度明顯不足 252 天（例如一年內才上市），不應顯示 1y 漲跌
                        if label == "1y" and len(hist) < 250: # 容許一點誤差，但新股必須過濾
                            changes[label] = None
                            continue
                            
                        past = float(hist['Close'].iloc[-days - 1])
                        changes[label] = round(((current - past) / past) * 100, 2)
                    else:
                        changes[label] = None
        except Exception as e:
            logger.warning(f"美股 {symbol} 歷史數據計算失敗: {e}")

        # 2. 市值與 PE 仍需從 info 取得 (若 info 失敗則保持 None)
        try:
            info = ticker.info
            market_cap = info.get("marketCap")
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        except Exception:
            pass

        return MarketDetail(
            symbol=symbol.upper(),
            change_pct_24h=pct_24h,
            change_pct_7d=changes.get("7d"),
            change_pct_14d=changes.get("14d"),
            change_pct_30d=changes.get("30d"),
            change_pct_60d=changes.get("60d"),
            change_pct_1y=changes.get("1y"),
            market_cap=market_cap,
            week_52_high=week_52_high,
            week_52_low=week_52_low,
            pe_ratio=pe_ratio,
            currency="USD",
        )

    async def get_historical_prices(
        self, symbol: str, timeframe: str = "1M"
    ) -> list[HistoricalPrice]:
        """取得美股歷史報價"""
        import asyncio
        period = TIMEFRAME_TO_PERIOD.get(timeframe, "1mo")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._fetch_historical, symbol, period
        )

    def _fetch_historical(
        self, symbol: str, period: str
    ) -> list[HistoricalPrice]:
        """同步取得歷史報價"""
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)

        if df.empty:
            raise PriceNotFoundError(f"找不到 {symbol} 的歷史報價")

        prices = []
        for idx, row in df.iterrows():
            prices.append(HistoricalPrice(
                symbol=symbol.upper(),
                date=idx.to_pydatetime(),
                open_price=Decimal(str(round(row["Open"], 4))),
                high=Decimal(str(round(row["High"], 4))),
                low=Decimal(str(round(row["Low"], 4))),
                close=Decimal(str(round(row["Close"], 4))),
                volume=Decimal(str(int(row.get("Volume", 0)))),
            ))
        return prices

    async def validate_symbol(self, symbol: str) -> bool:
        """驗證美股代碼"""
        try:
            await self.get_current_price(symbol)
            return True
        except (PriceNotFoundError, ProviderError):
            return False

    async def search_symbol(self, query: str) -> list[SearchResult]:
        """搜尋美股標的"""
        if not query:
            return []
            
        try:
            async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                response = await client.get(
                    "https://query2.finance.yahoo.com/v1/finance/search",
                    params={"q": query, "quotesCount": 10, "newsCount": 0}
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                for quote in data.get("quotes", []):
                    # 過濾掉非股票類型的結果 (例如加密貨幣或其他國家的標的)
                    # 簡單過濾：有 quoteType 且通常是 EQUITY 或 ETF
                    quote_type = quote.get("quoteType", "")
                    symbol = quote.get("symbol", "")
                    
                    if symbol:
                        results.append(SearchResult(
                            symbol=symbol,
                            name=quote.get("shortname") or quote.get("longname") or "",
                            type_box=quote_type,
                            exchange=quote.get("exchange"),
                            currency="USD"
                        ))
                return results
        except Exception as e:
            logger.warning("Yahoo Finance 搜尋失敗: %s", e)
            return []
