"""
定期定額計畫模型

管理用戶的定期定額投資設定與每次執行紀錄。
支援永豐豐存股等券商的定期定額排程。
"""

import json
import uuid
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Boolean, Date, DateTime, Numeric,
    ForeignKey, Enum, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvestmentType(str, enum.Enum):
    """投資模式列舉"""
    AMOUNT = "amount"   # 定額模式（固定金額）
    SHARES = "shares"   # 定股模式（固定股數）


class ExecutionStatus(str, enum.Enum):
    """執行狀態列舉"""
    PENDING = "pending"       # 待確認
    CONFIRMED = "confirmed"   # 已確認入帳
    SKIPPED = "skipped"       # 已跳過
    FAILED = "failed"         # 執行失敗


class DCASchedule(Base):
    """定期定額排程計畫"""
    __tablename__ = "dca_schedules"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    portfolio_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="標的代碼",
    )
    asset_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="標的名稱",
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("asset_categories.id"),
        nullable=False,
    )
    broker: Mapped[str] = mapped_column(
        String(20), default="sinopac",
        comment="券商識別",
    )
    investment_type: Mapped[InvestmentType] = mapped_column(
        Enum(InvestmentType), nullable=False,
    )
    target_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
        comment="目標金額（定額模式）",
    )
    target_shares: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True,
        comment="目標股數（定股模式）",
    )
    execution_days: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="扣款日 JSON，如 [3,16]",
    )
    fee_discount: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.1"),
        comment="手續費折扣",
    )
    auto_confirm: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="是否自動確認",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="是否啟用",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # 關聯
    user = relationship("User")
    portfolio = relationship("Portfolio")
    category = relationship("AssetCategory", lazy="selectin")
    executions: Mapped[list["DCAExecution"]] = relationship(
        "DCAExecution",
        back_populates="schedule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def get_execution_days(self) -> list[int]:
        """將 JSON 字串解析為扣款日列表"""
        try:
            return json.loads(self.execution_days)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_execution_days(self, days: list[int]) -> None:
        """設定扣款日列表為 JSON 字串"""
        self.execution_days = json.dumps(days)

    def __repr__(self) -> str:
        return f"<DCASchedule {self.symbol} {self.investment_type.value}>"


class DCAExecution(Base):
    """定期定額單次執行紀錄"""
    __tablename__ = "dca_executions"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id", "execution_date",
            name="uq_schedule_execution_date",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    schedule_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dca_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="執行日期",
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.PENDING,
    )
    estimated_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True,
        comment="系統估算價格（收盤價）",
    )
    actual_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True,
        comment="用戶確認的實際成交價",
    )
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True,
        comment="計算出的股數",
    )
    fee: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
        comment="手續費",
    )
    total_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True,
        comment="總扣款金額",
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("transactions.id"),
        nullable=True,
        comment="關聯的交易紀錄",
    )
    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # 關聯
    schedule: Mapped["DCASchedule"] = relationship(
        "DCASchedule", back_populates="executions",
    )
    transaction = relationship("Transaction")

    def __repr__(self) -> str:
        return (
            f"<DCAExecution {self.execution_date} "
            f"{self.status.value}>"
        )
