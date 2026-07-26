"""
定期定額相關 Schema

定義定期定額計畫、執行紀錄的請求與回應模型。
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.dca import InvestmentType, ExecutionStatus


class DCAScheduleCreate(BaseModel):
    """建立定期定額計畫請求"""
    portfolio_id: str
    symbol: str = Field(max_length=20)
    asset_name: str | None = Field(default=None, max_length=100)
    category_id: int = 1
    broker: str = Field(default="sinopac", max_length=20)
    investment_type: InvestmentType
    target_amount: Decimal | None = Field(default=None, ge=0)
    target_shares: Decimal | None = Field(default=None, gt=0)
    execution_days: list[int] = Field(
        ...,
        min_length=1,
        description="扣款日列表，每月的第幾天 (1-31)",
    )
    fee_discount: Decimal = Field(default=Decimal("0.1"), ge=0, le=1)
    auto_confirm: bool = False

    @model_validator(mode="after")
    def validate_investment_target(self) -> "DCAScheduleCreate":
        """驗證定額模式需有 target_amount，定股模式需有 target_shares"""
        if self.investment_type == InvestmentType.AMOUNT:
            if self.target_amount is None or self.target_amount <= 0:
                raise ValueError("定額模式必須設定 target_amount 且大於 0")
        elif self.investment_type == InvestmentType.SHARES:
            if self.target_shares is None or self.target_shares <= 0:
                raise ValueError("定股模式必須設定 target_shares 且大於 0")
        # 驗證扣款日範圍
        for day in self.execution_days:
            if day < 1 or day > 31:
                raise ValueError(
                    f"扣款日必須在 1-31 之間，收到: {day}"
                )
        return self


class DCAScheduleUpdate(BaseModel):
    """更新定期定額計畫請求（全部 optional）"""
    symbol: str | None = Field(default=None, max_length=20)
    asset_name: str | None = Field(default=None, max_length=100)
    category_id: int | None = None
    broker: str | None = Field(default=None, max_length=20)
    investment_type: InvestmentType | None = None
    target_amount: Decimal | None = Field(default=None, ge=0)
    target_shares: Decimal | None = Field(default=None, gt=0)
    execution_days: list[int] | None = None
    fee_discount: Decimal | None = Field(default=None, ge=0, le=1)
    auto_confirm: bool | None = None


class DCAScheduleResponse(BaseModel):
    """定期定額計畫完整回應"""
    id: str
    user_id: str
    portfolio_id: str
    symbol: str
    asset_name: str | None
    category_id: int
    broker: str
    investment_type: InvestmentType
    target_amount: Decimal | None
    target_shares: Decimal | None
    execution_days: list[int]
    fee_discount: Decimal
    auto_confirm: bool
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    next_execution_date: date | None = None
    pending_count: int = 0

    model_config = {"from_attributes": True}


class DCAExecutionResponse(BaseModel):
    """定期定額執行紀錄回應"""
    id: str
    schedule_id: str
    execution_date: date
    status: ExecutionStatus
    estimated_price: Decimal | None
    actual_price: Decimal | None
    quantity: Decimal | None
    fee: Decimal | None
    total_cost: Decimal | None
    transaction_id: str | None
    note: str | None
    created_at: datetime | None = None
    confirmed_at: datetime | None = None
    # 來自關聯 schedule 的欄位
    schedule_symbol: str | None = None
    schedule_asset_name: str | None = None

    model_config = {"from_attributes": True}


class DCAExecutionConfirm(BaseModel):
    """確認定期定額執行請求"""
    actual_price: Decimal | None = Field(default=None, gt=0)
    note: str | None = None


class DCABatchConfirmResult(BaseModel):
    """批次確認結果"""
    total: int
    confirmed: int
    failed: int
    errors: list[str]


class DCAImportRecord(BaseModel):
    """單筆匯入後的定期定額扣款紀錄"""
    source_row: int | None = Field(
        default=None,
        description="來源 CSV 列號（含標題列，資料列從 2 起算）",
    )
    execution_date: date
    symbol: str = Field(max_length=20)
    asset_name: str | None = Field(default=None, max_length=100)
    broker: str | None = Field(default=None, max_length=20)
    investment_type: InvestmentType = InvestmentType.AMOUNT
    target_amount: Decimal | None = Field(default=None, ge=0)
    target_shares: Decimal | None = Field(default=None, gt=0)
    execution_days: list[int] | None = None
    actual_price: Decimal | None = Field(default=None, gt=0)
    quantity: Decimal | None = Field(default=None, gt=0)
    fee: Decimal | None = Field(default=None, ge=0)
    total_cost: Decimal | None = Field(default=None, ge=0)
    currency: str = "TWD"
    status: ExecutionStatus | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_import_values(self) -> "DCAImportRecord":
        """匯入資料至少要能推導出單次扣款內容。"""
        if self.target_amount is None and self.target_shares is None:
            if self.total_cost is not None:
                self.target_amount = self.total_cost
            elif self.quantity is not None:
                self.target_shares = self.quantity

        if self.execution_days is None:
            self.execution_days = [self.execution_date.day]

        for day in self.execution_days:
            if day < 1 or day > 31:
                raise ValueError(f"扣款日必須在 1-31 之間，收到: {day}")

        return self


class DCAImportRowDetail(BaseModel):
    """單列匯入（或預覽）結果明細"""
    row: int
    symbol: str | None = None
    asset_name: str | None = None
    broker: str | None = None
    execution_date: date | None = None
    actual_price: Decimal | None = None
    quantity: Decimal | None = None
    total_cost: Decimal | None = None
    status: str = "ok"  # ok / error
    schedule_action: str = "none"  # create / update / unchanged / none
    execution_action: str = "none"  # create / update / none
    transaction_action: str = "none"  # create / update / none
    error: str | None = None


class DCAImportColumnInfo(BaseModel):
    """匯入 CSV 支援欄位與別名對照"""
    key: str
    label: str
    required: bool
    aliases: list[str]
    description: str


class DCAImportResult(BaseModel):
    """定期定額匯入結果"""
    total_rows: int
    imported: int
    skipped: int
    schedules_created: int
    schedules_updated: int
    executions_created: int
    executions_updated: int
    transactions_created: int
    transactions_updated: int
    errors: list[str]
    dry_run: bool = False
    details: list[DCAImportRowDetail] = Field(default_factory=list)
