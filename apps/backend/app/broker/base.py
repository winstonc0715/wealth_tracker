"""
券商同步服務基礎類別

Phase 1: CSV 匯入 + 部位比對
Phase 2 (未來): Plaid / 授權 API 自動同步
"""

from abc import ABC, abstractmethod
from typing import Any


class BrokerSyncService(ABC):
    """
    券商同步服務抽象類別

    Phase 2 預留介面，待核心穩定後實作。
    """

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> bool:
        """
        OAuth 授權流程

        Args:
            credentials: 授權憑證（token, client_id 等）
        """
        ...

    @abstractmethod
    async def fetch_positions(self) -> list[dict[str, Any]]:
        """從券商 API 取得目前持倉"""
        ...

    @abstractmethod
    async def fetch_transactions(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """從券商 API 取得交易紀錄"""
        ...


class PlaidBrokerService(BrokerSyncService):
    """
    Plaid 券商同步（Phase 2 預留）

    支援部分美股券商與加密貨幣交易所。
    """

    async def authenticate(self, credentials: dict[str, Any]) -> bool:
        # TODO: Phase 2 實作 Plaid Link 整合
        raise NotImplementedError("Plaid 整合尚在開發中")

    async def fetch_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Plaid 整合尚在開發中")

    async def fetch_transactions(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Plaid 整合尚在開發中")
