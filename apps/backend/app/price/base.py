"""
報價提供者抽象基礎類別

定義所有報價來源必須實作的介面。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class PriceData:
    """報價資料"""
    symbol: str
    price: Decimal
    currency: str
    timestamp: datetime = field(default_factory=datetime.now)
    change_24h: Decimal | None = None
    change_pct_24h: Decimal | None = None
    source: str = ""


@dataclass
class SearchResult:
    """搜尋結果資料"""
    symbol: str
    name: str
    type_box: str | None = None  # 例如 "ETF", "Equity", "Crypto"
    exchange: str | None = None  # 例如 "TWSE", "NASDAQ"
    currency: str | None = None
    category_slug: str | None = None  # 自動判斷的資產類別


@dataclass
class HistoricalPrice:
    """歷史報價資料"""
    symbol: str
    date: datetime
    open_price: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None


class PriceProvider(ABC):
    """
    報價提供者抽象類別

    所有報價來源（CoinGecko、Yahoo Finance、Fugle 等）
    必須繼承此類別並實作以下方法。
    """

    @abstractmethod
    async def get_current_price(self, symbol: str) -> PriceData:
        """
        取得指定標的的即時報價。

        Args:
            symbol: 標的代碼（如 BTC, AAPL, 2330.TW）

        Returns:
            PriceData 物件

        Raises:
            PriceNotFoundError: 找不到報價
            ProviderError: API 呼叫失敗
        """
        ...

    @abstractmethod
    async def get_historical_prices(
        self, symbol: str, timeframe: str = "1M"
    ) -> list[HistoricalPrice]:
        """
        取得歷史報價。

        Args:
            symbol: 標的代碼
            timeframe: 時間範圍 (1W, 1M, 3M, 6M, 1Y, 5Y)

        Returns:
            HistoricalPrice 列表
        """
        ...

    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """驗證標的代碼是否有效"""
        ...

    @abstractmethod
    async def search_symbol(self, query: str) -> list[SearchResult]:
        """
        搜尋標的
        
        Args:
            query: 搜尋關鍵字 (代碼或名稱)
            
        Returns:
            SearchResult 列表，最多返回前 10 筆
        """
        ...


class PriceNotFoundError(Exception):
    """找不到報價"""
    pass


class ProviderError(Exception):
    """報價提供者錯誤"""
    pass
