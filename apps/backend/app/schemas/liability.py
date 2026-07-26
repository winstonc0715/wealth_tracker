"""
負債管理相關 Schema
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.liability import PaymentCycle


class LiabilityCreate(BaseModel):
    """新增負債請求"""
    portfolio_id: str
    name: str = Field(max_length=100)
    principal: Decimal = Field(gt=0, description="原始本金總額")
    payment_cycle: PaymentCycle = PaymentCycle.MONTHLY
    total_periods: int = Field(gt=0, le=1200)
    payment_amount: Decimal = Field(gt=0, description="每期還款金額")
    payment_day: int | None = Field(default=None, ge=1, le=31)
    start_date: date | None = None
    currency: str = "TWD"
    note: str | None = Field(default=None, max_length=500)
    # 綁定既有負債持倉的代號；不填則自動建立新持倉
    existing_symbol: str | None = Field(default=None, max_length=20)


class LiabilityUpdate(BaseModel):
    """更新負債請求"""
    name: str | None = Field(default=None, max_length=100)
    payment_cycle: PaymentCycle | None = None
    total_periods: int | None = Field(default=None, gt=0, le=1200)
    payment_amount: Decimal | None = Field(default=None, gt=0)
    payment_day: int | None = Field(default=None, ge=1, le=31)
    start_date: date | None = None
    note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    # 直接校正剩餘金額（如對齊銀行剩餘本金）；會建立調整交易，不影響還款紀錄
    outstanding_balance: Decimal | None = Field(default=None, ge=0)


class PaymentCreate(BaseModel):
    """記錄還款請求"""
    amount: Decimal = Field(gt=0)
    payment_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


class PaymentResponse(BaseModel):
    """還款紀錄回應"""
    id: str
    payment_date: date
    amount: Decimal
    transaction_id: str | None
    note: str | None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BackfillPreview(BaseModel):
    """補登預覽：依日期推算的待補期數與金額"""
    expected_periods: int
    paid_periods: int
    pending_periods: int
    pending_amount: Decimal = Decimal("0")
    first_date: date | None = None
    last_date: date | None = None
    # 偵測到的重複自動補登紀錄數（可一鍵清理）
    duplicate_payments: int = 0


class LiabilityResponse(BaseModel):
    """負債回應（含進度統計）"""
    id: str
    portfolio_id: str
    symbol: str
    name: str
    principal: Decimal
    payment_cycle: PaymentCycle
    total_periods: int
    payment_amount: Decimal
    payment_day: int | None
    start_date: date | None
    currency: str
    note: str | None
    is_active: bool
    created_at: datetime | None = None

    # 進度統計（由 service 計算）
    outstanding_balance: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    paid_periods: int = 0
    # 依今日日期推算應已繳的期數（供前端顯示落後提示）
    expected_periods: int = 0
    progress_pct: float = 0.0
    next_payment_date: date | None = None
    payments: list[PaymentResponse] = []

    model_config = {"from_attributes": True}
