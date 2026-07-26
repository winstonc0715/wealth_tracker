"""
投資組合模型

一個用戶可擁有多個投資組合（如「長期投資」、「短線操作」）。
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    base_currency: Mapped[str] = mapped_column(
        String(10), default="TWD", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 關聯
    # lazy="raise"：這些集合會隨歷史成長到數千筆，原本的 selectin
    # 讓「每個請求的身份驗證/歸屬檢查」都把全部交易與快照撈進記憶體。
    # 服務層一律以明確 select 查詢，誤觸集合屬性時直接報錯提醒。
    # passive_deletes：刪除投資組合交由 DB 的 ondelete CASCADE 處理。
    user = relationship("User", back_populates="portfolios")
    transactions = relationship(
        "Transaction", back_populates="portfolio",
        lazy="raise", passive_deletes=True,
    )
    positions = relationship(
        "CurrentPosition", back_populates="portfolio",
        lazy="raise", passive_deletes=True,
    )
    net_worth_history = relationship(
        "HistoricalNetWorth", back_populates="portfolio",
        lazy="raise", passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Portfolio {self.name}>"
