"""
投資組合相關 Schema

定義投資組合 CRUD、淨值摘要、資產配置的請求與回應模型。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    """建立投資組合"""
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    base_currency: str = "TWD"


class PortfolioUpdate(BaseModel):
    """更新投資組合"""
    name: str | None = None
    description: str | None = None


class PortfolioResponse(BaseModel):
    """投資組合回應"""
    id: str
    name: str
    description: str | None
    base_currency: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PositionDetail(BaseModel):
    """持倉明細（含即時價格與損益）"""
    symbol: str
    name: str | None
    category_slug: str
    total_quantity: Decimal
    avg_cost: Decimal
    current_price: Decimal
    total_value: Decimal
    total_cost: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    currency: str
    price_change_24h_pct: Decimal | None = None
    total_value_base: Decimal | None = None
    unrealized_pnl_base: Decimal | None = None
    current_price_base: Decimal | None = None


class PortfolioSummary(BaseModel):
    """投資組合淨值摘要"""
    portfolio_id: str
    portfolio_name: str
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    positions: list[PositionDetail]
    last_updated: datetime


class AllocationItem(BaseModel):
    """資產配置項目（圓餅圖用）"""
    category: str
    category_slug: str
    value: Decimal
    percentage: Decimal
    color: str | None = None


class AllocationResponse(BaseModel):
    """資產配置回應"""
    portfolio_id: str
    total_value: Decimal
    allocations: list[AllocationItem]


class NetWorthHistoryItem(BaseModel):
    """單日淨值歷史紀錄"""
    date: str
    value: Decimal


class PortfolioHistoryResponse(BaseModel):
    """投資組合歷史淨值走勢"""
    portfolio_id: str
    history: list[NetWorthHistoryItem]
