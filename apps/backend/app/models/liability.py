"""
負債管理模型

管理用戶的負債（貸款/信用卡等）設定與還款紀錄。
負債餘額仍以 category=liability 的 CurrentPosition 呈現，
本表補上還款週期、期數、金額等金融屬性與還款歷史。
"""

import uuid
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Boolean, Date, DateTime, Numeric,
    ForeignKey, Enum, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaymentCycle(str, enum.Enum):
    """還款週期列舉"""
    WEEKLY = "weekly"        # 每週
    BIWEEKLY = "biweekly"    # 每兩週
    MONTHLY = "monthly"      # 每月
    QUARTERLY = "quarterly"  # 每季


class Liability(Base):
    """負債主檔"""
    __tablename__ = "liabilities"

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
        comment="對應持倉的標的代號",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="負債名稱，如「房貸」「車貸」",
    )
    principal: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False,
        comment="原始本金總額",
    )
    payment_cycle: Mapped[PaymentCycle] = mapped_column(
        Enum(PaymentCycle), default=PaymentCycle.MONTHLY,
        comment="還款週期",
    )
    total_periods: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="總期數",
    )
    payment_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False,
        comment="每期還款金額",
    )
    payment_day: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="每期繳款日（1-31，週期為月/季時適用）",
    )
    start_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="起始日",
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="TWD",
    )
    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="是否進行中（結清後為 False）",
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
    payments: Mapped[list["LiabilityPayment"]] = relationship(
        "LiabilityPayment",
        back_populates="liability",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LiabilityPayment.payment_date",
    )

    def __repr__(self) -> str:
        return f"<Liability {self.name} {self.principal}>"


class LiabilityPayment(Base):
    """單次還款紀錄"""
    __tablename__ = "liability_payments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    liability_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("liabilities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="還款日期",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False,
        comment="還款金額",
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("transactions.id"),
        nullable=True,
        comment="關聯的沖減交易",
    )
    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # 關聯
    liability: Mapped["Liability"] = relationship(
        "Liability", back_populates="payments",
    )
    transaction = relationship("Transaction")

    def __repr__(self) -> str:
        return f"<LiabilityPayment {self.payment_date} {self.amount}>"
