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
            
            if raw_price == "-":
                raw_price = ""

            # 處理 13:25-13:30 試撮期間無 latest_trade_price 的狀況
            if not raw_price:
                bids = real_data.get("best_bid_price", [])
                if bids and bids[0] and bids[0] != "-":
                    raw_price = bids[0].strip().replace(",", "")
            
            price = Decimal(raw_price) if raw_price else Decimal("0")

            if price == 0:
                # 無成交價且無買價時 fallback 至 TWSE API
                logger.warning(f"twstock {stock_id} 無成交價與試撮價，切換至 TWSE API")
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
            
            # z 是當盤成交價，如果為 "-" 代表還沒開盤或正在試撮 (如 13:25-13:30)
            z_price = stock_data.get("z", "")
            if not z_price or z_price == "-":
                # 尋求試撮價格 (pz)
                pz_price = stock_data.get("pz", "")
                if pz_price and pz_price != "-":
                    price = Decimal(pz_price.replace(",", ""))
                else:
                    # 尋求第一檔委買價 (b)
                    b_str = stock_data.get("b", "")
                    b_prices = [p for p in b_str.split("_") if p and p != "-"]
                    if b_prices:
                        price = Decimal(b_prices[0].replace(",", ""))
                    else:
                        price = yesterday
            else:
                price = Decimal(z_price.replace(",", ""))

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

    async def get_market_detail(self, symbol: str) -> "MarketDetail":
        """取得台股市場詳情（52W、多時段漲跌）"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_market_detail, symbol)

    def _fetch_market_detail(self, symbol: str) -> "MarketDetail":
        """同步取得台股市場詳情 (twstock + yfinance 備援)"""
        from app.price.base import MarketDetail
        import yfinance as yf

        stock_id = symbol.replace(".TW", "").replace(".TWO", "")
        changes: dict[str, float | None] = {}
        week_52_high = None
        week_52_low = None

        # 1. 嘗試透過 yfinance 取得穩定數據 (備援優先，因為爬蟲在雲端太常失敗)
        try:
            # 判斷是上市 (.TW) 還是上櫃 (.TWO)
            yf_symbol = f"{stock_id}.TW"
            ticker = yf.Ticker(yf_symbol)
            # 先試 .TW，如果沒數據再試 .TWO
            hist = ticker.history(period="1y")
            
            if hist.empty:
                yf_symbol = f"{stock_id}.TWO"
                ticker = yf.Ticker(yf_symbol)
                hist = ticker.history(period="1y")

            if not hist.empty:
                # 計算 52W 高低
                week_52_high = float(hist['High'].max())
                week_52_low = float(hist['Low'].min())
                
                # 計算各時段漲跌
                current = float(hist['Close'].iloc[-1])
                # yf 返回的是交易日數據，用估算的天數 (1週~5天, 1月~22天)
                intervals = [("7d", 5), ("14d", 10), ("30d", 22), ("60d", 44), ("1y", 252)]
                for label, days in intervals:
                    if len(hist) > days:
                        past = float(hist['Close'].iloc[-days-1])
                        changes[label] = round(((current - past) / past) * 100, 2)
                
                logger.info(f"台股 {stock_id} 透過 yfinance 取得數據成功")
        except Exception as e:
            logger.warning(f"台股 {stock_id} yfinance 備援失敗: {e}")

        # 2. 如果 yfinance 沒抓到，嘗試 twstock (爬蟲)
        if not changes and not week_52_high:
            try:
                import twstock
                stock = twstock.Stock(stock_id)
                data = stock.fetch_from(datetime.now().year - 1, datetime.now().month)
                if data:
                    closes = [d.close for d in data if d.close]
                    highs = [d.high for d in data if d.high]
                    lows = [d.low for d in data if d.low]

                    if closes:
                        current = float(closes[-1])
                        for label, days in [("7d", 5), ("14d", 10), ("30d", 22), ("60d", 44), ("1y", 252)]:
                            if len(closes) > days:
                                past = float(closes[-days - 1])
                                changes[label] = round(((current - past) / past) * 100, 2)
                    if highs: week_52_high = float(max(highs))
                    if lows: week_52_low = float(min(lows))
            except Exception as e:
                logger.warning(f"台股 {stock_id} twstock 取得失敗: {e}")

        # 3. 24h 漲跌從現有即時報價取得
        pct_24h = None
        try:
            price_data = self._fetch_price(symbol)
            if price_data.change_pct_24h is not None:
                pct_24h = float(price_data.change_pct_24h)
        except Exception:
            pass

        return MarketDetail(
            symbol=stock_id,
            change_pct_24h=pct_24h,
            change_pct_7d=changes.get("7d"),
            change_pct_14d=changes.get("14d"),
            change_pct_30d=changes.get("30d"),
            change_pct_60d=changes.get("60d"),
            change_pct_1y=changes.get("1y"),
            week_52_high=week_52_high,
            week_52_low=week_52_low,
            currency="TWD",
        )

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
