"""
交易明細模型

紀錄每一筆買入、賣出、配息交易，
含時間戳記、數量、單價、手續費等完整資訊。
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, DateTime, Numeric,
    ForeignKey, Enum, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class TransactionType(str, enum.Enum):
    """交易類型列舉"""
    BUY = "buy"          # 買入
    SELL = "sell"         # 賣出
    DIVIDEND = "dividend" # 配息
    DEPOSIT = "deposit"   # 存入（法幣）
    WITHDRAW = "withdraw" # 提出（法幣）


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    portfolio_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("asset_categories.id"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="標的代碼，如 2330.TW, AAPL, BTC",
    )
    asset_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="標的名稱，如 台積電、Apple",
    )
    tx_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType), nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False,
        comment="交易數量（加密貨幣支援小數）",
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False,
        comment="單位價格",
    )
    fee: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=4), default=Decimal("0"),
        comment="手續費",
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="TWD",
        comment="交易幣別",
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="交易執行時間",
    )
    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="備註",
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=4), default=Decimal("0"),
        comment="已實現損益 (僅 SELL/DIVIDEND 類型有值)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # 關聯
    portfolio = relationship("Portfolio", back_populates="transactions")
    category = relationship("AssetCategory", lazy="selectin")

    @property
    def total_amount(self) -> Decimal:
        """交易總金額（含手續費）"""
        return self.quantity * self.unit_price + self.fee

    def __repr__(self) -> str:
        return f"<Transaction {self.tx_type.value} {self.symbol} x{self.quantity}>"
