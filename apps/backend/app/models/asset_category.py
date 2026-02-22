"""
資產類別模型

定義資產分類：台股、美股、加密貨幣、法幣、負債。
系統初始化時預設寫入這些類別。
"""

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssetCategory(Base):
    __tablename__ = "asset_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<AssetCategory {self.name}>"


# 預設資產類別
DEFAULT_CATEGORIES = [
    {"name": "台股", "slug": "tw_stock", "description": "台灣上市櫃股票"},
    {"name": "美股", "slug": "us_stock", "description": "美國上市股票與 ETF"},
    {"name": "加密貨幣", "slug": "crypto", "description": "比特幣、以太幣等加密資產"},
    {"name": "法幣", "slug": "fiat", "description": "法定貨幣（美元、台幣現金等）"},
    {"name": "負債", "slug": "liability", "description": "貸款、信用卡等負債項目"},
]
