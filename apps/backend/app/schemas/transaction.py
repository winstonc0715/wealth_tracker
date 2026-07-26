"""
交易相關 Schema

定義新增交易、交易紀錄查詢的請求與回應模型。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.transaction import TransactionType


class TransactionCreate(BaseModel):
    """新增交易請求"""
    portfolio_id: str
    category_id: int
    symbol: str = Field(max_length=20)
    asset_name: str | None = Field(default=None, max_length=100)
    tx_type: TransactionType
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = "TWD"
    executed_at: datetime
    note: str | None = None


class TransactionUpdate(BaseModel):
    """更新交易請求"""
    category_id: int | None = None
    symbol: str | None = Field(default=None, max_length=20)
    asset_name: str | None = Field(default=None, max_length=100)
    tx_type: TransactionType | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    fee: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    executed_at: datetime | None = None
    note: str | None = None

class PositionAssetUpdate(BaseModel):
    """
    修改持倉標的屬性請求

    用於修正選錯市場/幣別的持倉（例如誤選美股 0050，實為台股 0050）。
    會同步更新該標的底下所有交易紀錄並全量重算持倉。
    """
    category_id: int | None = Field(default=None, ge=1)
    symbol: str | None = Field(default=None, max_length=20)
    name: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    # 直接指定目標持倉數量/平均成本（以調整交易方式達成，不破壞交易歷史）
    total_quantity: Decimal | None = Field(default=None, ge=0)
    avg_cost: Decimal | None = Field(default=None, ge=0)


class TransactionResponse(BaseModel):
    """交易紀錄回應"""
    id: str
    portfolio_id: str
    category_id: int
    category_name: str | None = None
    symbol: str
    asset_name: str | None
    tx_type: TransactionType
    quantity: Decimal
    unit_price: Decimal
    fee: Decimal
    currency: str
    executed_at: datetime
    note: str | None
    realized_pnl: Decimal = Decimal("0")
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CSVImportRequest(BaseModel):
    """CSV 匯入請求"""
    portfolio_id: str
    broker_format: str = "standard"  # standard, sinopac, fubon, cathay


class CSVImportResult(BaseModel):
    """CSV 匯入結果"""
    total_rows: int
    imported: int
    skipped: int
    errors: list[str]


class ReconciliationItem(BaseModel):
    """部位比對項目"""
    symbol: str
    system_quantity: Decimal
    external_quantity: Decimal
    difference: Decimal
    status: str  # matched, mismatch, missing_in_system, missing_in_external


class ReconciliationResult(BaseModel):
    """部位比對結果"""
    portfolio_id: str
    total_symbols: int
    matched: int
    mismatched: int
    items: list[ReconciliationItem]
