"""
台股報價提供者

透過 twstock 或公開資料 API 取得台灣上市櫃股票報價。
twstock 為開源 Python 套件，無需 API Key。
"""

import logging
from datetime import datetime
from decimal import Decimal

from app.price.base import (
    PriceProvider, PriceData, HistoricalPrice,
    PriceNotFoundError, ProviderError, SearchResult
)

logger = logging.getLogger(__name__)


class TWStockProvider(PriceProvider):
    """台股報價提供者（twstock + TWSE 公開資料）"""

    async def get_current_price(self, symbol: str) -> PriceData:
        """取得台股即時報價"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._fetch_price, symbol
            )
        except Exception as e:
            if isinstance(e, (PriceNotFoundError, ProviderError)):
                raise
            raise ProviderError(f"台股報價錯誤: {e}") from e

    def _fetch_price(self, symbol: str) -> PriceData:
        """同步取得台股報價（twstock 優先，失敗時自動 fallback 至 TWSE API）"""
        # 移除 .TW 或 .TWO 後綴
        stock_id = symbol.replace(".TW", "").replace(".TWO", "")

        try:
            import twstock
            stock = twstock.realtime.get(stock_id)

            if not stock or not stock.get("success"):
                # twstock 查詢失敗（常見於 ETF），改用 TWSE API
                logger.warning(f"twstock 查詢 {stock_id} 失敗，切換至 TWSE API")
                return self._fetch_from_twse(stock_id)

            real_data = stock["realtime"]
            raw_price = real_data.get("latest_trade_price", "") or ""
            # 清理價格字串（移除空白、逗號等）
            raw_price = raw_price.strip().replace(",", "")
            price = Decimal(raw_price) if raw_price else Decimal("0")

            if price == 0:
                # 無成交價時 fallback 至 TWSE API
                logger.warning(f"twstock {stock_id} 無成交價，切換至 TWSE API")
                return self._fetch_from_twse(stock_id)

            # 計算漲跌幅
            yesterday_close = Decimal(str(real_data.get("open", price)))

            change_24h = None
            change_pct = None
            if yesterday_close > 0:
                change_24h = price - yesterday_close
                change_pct = (change_24h / yesterday_close) * 100

            return PriceData(
                symbol=stock_id,
                price=price,
                currency="TWD",
                timestamp=datetime.now(),
                change_24h=change_24h,
                change_pct_24h=change_pct,
                source="twstock",
            )
        except ImportError:
            # twstock 未安裝時，透過 TWSE API 取得
            return self._fetch_from_twse(stock_id)
        except Exception as e:
            # 任何其他錯誤也 fallback 至 TWSE API
            logger.warning(f"twstock 查詢 {stock_id} 異常: {e}，切換至 TWSE API")
            return self._fetch_from_twse(stock_id)

    def _fetch_from_twse(self, stock_id: str) -> PriceData:
        """備用：透過證交所 API 取得報價"""
        import httpx

        url = (
            "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
            f"?ex_ch=tse_{stock_id}.tw"
        )
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("msgArray"):
                raise PriceNotFoundError(f"找不到台股 {stock_id}")

            stock_data = data["msgArray"][0]
            yesterday_str = stock_data.get("y", "0")
            yesterday = Decimal(yesterday_str) if yesterday_str and yesterday_str != "-" else Decimal("0")
            
            # z 是當盤成交價，如果為 "-" 代表還沒開盤或沒有成交，就用昨收價
            z_price = stock_data.get("z", "")
            if not z_price or z_price == "-":
                price = yesterday
            else:
                price = Decimal(z_price)

            change = None
            change_pct = None
            if yesterday > 0 and price > 0:
                change = price - yesterday
                change_pct = (change / yesterday) * 100

            return PriceData(
                symbol=stock_id,
                price=price,
                currency="TWD",
                timestamp=datetime.now(),
                change_24h=change,
                change_pct_24h=change_pct,
                source="twse",
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"TWSE API 錯誤: {e}") from e

    async def get_historical_prices(
        self, symbol: str, timeframe: str = "1M"
    ) -> list[HistoricalPrice]:
        """取得台股歷史報價"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._fetch_historical, symbol, timeframe
        )

    def _fetch_historical(
        self, symbol: str, timeframe: str
    ) -> list[HistoricalPrice]:
        """同步取得台股歷史報價"""
        stock_id = symbol.replace(".TW", "").replace(".TWO", "")

        try:
            import twstock
            stock = twstock.Stock(stock_id)
            # twstock 預設取得近 31 天資料
            data = stock.data

            if not data:
                raise PriceNotFoundError(f"找不到台股 {stock_id} 歷史資料")

            prices = []
            for d in data:
                prices.append(HistoricalPrice(
                    symbol=stock_id,
                    date=d.date if isinstance(d.date, datetime) else datetime.combine(d.date, datetime.min.time()),
                    open_price=Decimal(str(d.open)),
                    high=Decimal(str(d.high)),
                    low=Decimal(str(d.low)),
                    close=Decimal(str(d.close)),
                    volume=Decimal(str(d.turnover)),
                ))
            return prices
        except ImportError:
            logger.warning("twstock 未安裝，台股歷史資料暫不可用")
            return []

    async def validate_symbol(self, symbol: str) -> bool:
        """驗證台股代碼"""
        try:
            await self.get_current_price(symbol)
            return True
        except (PriceNotFoundError, ProviderError):
            return False

    async def search_symbol(self, query: str) -> list[SearchResult]:
        """搜尋台股標的"""
        if not query:
            return []
            
        try:
            # 由於 twstock 查詢需加載字典較慢，將其放入 executor 並快取
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._search_sync, query)
        except Exception as e:
            logger.warning("TWStock 搜尋失敗: %s", e)
            return []
            
    def _search_sync(self, query: str) -> list[SearchResult]:
        import twstock
        results = []
        query_upper = query.upper()
        
        # 遍歷 twstock 的代碼表
        for code, info in twstock.codes.items():
            if query_upper in code or query_upper in info.name:
                results.append(SearchResult(
                    symbol=code,
                    name=info.name,
                    type_box=info.type,
                    exchange="TWSE" if info.market == "上市" else "TPEx",
                    currency="TWD"
                ))
            if len(results) >= 15:
                break
        return results
