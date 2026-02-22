"""
當前持有部位模型

由 transactions 聚合而成，紀錄每個標的的總數量與平均成本。
每次新增交易時自動重新計算。
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, DateTime, Numeric,
    ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CurrentPosition(Base):
    __tablename__ = "current_positions"

    # 同一投資組合內，symbol 必須唯一
    __table_args__ = (
        UniqueConstraint("portfolio_id", "symbol", name="uq_portfolio_symbol"),
    )

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
        comment="標的代碼",
    )
    name: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="標的名稱",
    )
    total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), default=Decimal("0"),
        comment="總持有數量",
    )
    avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), default=Decimal("0"),
        comment="加權平均成本",
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="TWD",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 關聯
    portfolio = relationship("Portfolio", back_populates="positions")
    category = relationship("AssetCategory", lazy="selectin")

    @property
    def total_cost(self) -> Decimal:
        """總投入成本"""
        return self.total_quantity * self.avg_cost

    def __repr__(self) -> str:
        return f"<Position {self.symbol} qty={self.total_quantity}>"
