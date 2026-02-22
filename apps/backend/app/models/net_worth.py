"""
歷史淨值快照模型

每日排程結算寫入，用於繪製淨值趨勢圖。
breakdown 欄位以 JSON 儲存各類別的資產明細。
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String, Date, DateTime, Numeric, JSON,
    ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HistoricalNetWorth(Base):
    __tablename__ = "historical_net_worth"

    # 同一投資組合同一天只能有一筆快照
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "snapshot_date",
            name="uq_portfolio_date",
        ),
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
    snapshot_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True,
        comment="快照日期",
    )
    total_assets: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=4), default=Decimal("0"),
        comment="總資產價值",
    )
    total_liabilities: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=4), default=Decimal("0"),
        comment="總負債價值",
    )
    net_worth: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=4), default=Decimal("0"),
        comment="淨值 = 總資產 - 總負債",
    )
    breakdown: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="各類別資產明細 JSON",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # 關聯
    portfolio = relationship("Portfolio", back_populates="net_worth_history")

    def __repr__(self) -> str:
        return f"<NetWorth {self.snapshot_date} = {self.net_worth}>"
