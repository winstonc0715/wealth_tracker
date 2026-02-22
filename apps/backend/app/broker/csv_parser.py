"""
CSV 解析器

支援標準格式與主流台灣券商對帳單解析。
將不同格式統一轉換為系統內部的交易格式。
"""

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.transaction import TransactionCreate

logger = logging.getLogger(__name__)


# 券商對帳單欄位對應表
BROKER_FIELD_MAPS: dict[str, dict[str, str]] = {
    # 標準格式：日期, 標的代碼, 交易類型, 數量, 價格, 手續費
    "standard": {
        "date": "date",
        "symbol": "symbol",
        "type": "type",
        "quantity": "quantity",
        "price": "price",
        "fee": "fee",
        "name": "name",
    },
    # 永豐金證券
    "sinopac": {
        "date": "成交日期",
        "symbol": "股票代號",
        "type": "買賣別",
        "quantity": "成交股數",
        "price": "成交價格",
        "fee": "手續費",
        "name": "股票名稱",
    },
    # 富邦證券
    "fubon": {
        "date": "交易日期",
        "symbol": "證券代號",
        "type": "交易類別",
        "quantity": "成交數量",
        "price": "成交單價",
        "fee": "手續費",
        "name": "證券名稱",
    },
    # 國泰證券
    "cathay": {
        "date": "成交日期",
        "symbol": "證券代號",
        "type": "買/賣",
        "quantity": "成交股數",
        "price": "成交價格",
        "fee": "手續費",
        "name": "證券名稱",
    },
}

# 交易類型對應
TX_TYPE_MAP: dict[str, str] = {
    "buy": "buy", "買": "buy", "買進": "buy", "B": "buy",
    "sell": "sell", "賣": "sell", "賣出": "sell", "S": "sell",
    "dividend": "dividend", "配息": "dividend", "股利": "dividend",
    "deposit": "deposit", "存入": "deposit",
    "withdraw": "withdraw", "提出": "withdraw",
}


class CSVParser:
    """券商對帳單 CSV 解析器"""

    def __init__(self, broker_format: str = "standard"):
        if broker_format not in BROKER_FIELD_MAPS:
            raise ValueError(f"不支援的券商格式: {broker_format}")
        self.format = broker_format
        self.field_map = BROKER_FIELD_MAPS[broker_format]

    def parse(
        self,
        csv_content: str,
        portfolio_id: str,
        category_id: int,
    ) -> tuple[list[TransactionCreate], list[str]]:
        """
        解析 CSV 內容，回傳交易清單與錯誤列表。

        Args:
            csv_content: CSV 原始文字
            portfolio_id: 投資組合 ID
            category_id: 預設資產類別 ID

        Returns:
            (成功解析的交易列表, 錯誤訊息列表)
        """
        transactions: list[TransactionCreate] = []
        errors: list[str] = []

        reader = csv.DictReader(io.StringIO(csv_content))
        for row_num, row in enumerate(reader, start=2):
            try:
                tx = self._parse_row(row, portfolio_id, category_id)
                transactions.append(tx)
            except Exception as e:
                errors.append(f"第 {row_num} 行: {e}")
                logger.warning("CSV 解析第 %d 行失敗: %s", row_num, e)

        return transactions, errors

    def _parse_row(
        self,
        row: dict[str, Any],
        portfolio_id: str,
        category_id: int,
    ) -> TransactionCreate:
        """解析單行資料"""
        fm = self.field_map

        # 取欄位值（嘗試多種格式）
        date_str = self._get_field(row, fm["date"])
        symbol = self._get_field(row, fm["symbol"]).strip()
        tx_type_raw = self._get_field(row, fm["type"]).strip()
        quantity_str = self._get_field(row, fm["quantity"])
        price_str = self._get_field(row, fm["price"])
        fee_str = self._get_field(row, fm.get("fee", ""), default="0")
        name = self._get_field(row, fm.get("name", ""), default=None)

        # 轉換交易類型
        tx_type = TX_TYPE_MAP.get(tx_type_raw.lower())
        if not tx_type:
            raise ValueError(f"無法辨識交易類型: {tx_type_raw}")

        # 解析數值
        try:
            quantity = Decimal(quantity_str.replace(",", ""))
            unit_price = Decimal(price_str.replace(",", ""))
            fee = Decimal(fee_str.replace(",", "")) if fee_str else Decimal("0")
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"數值解析錯誤: {e}") from e

        # 解析日期
        executed_at = self._parse_date(date_str)

        return TransactionCreate(
            portfolio_id=portfolio_id,
            category_id=category_id,
            symbol=symbol,
            asset_name=name,
            tx_type=tx_type,
            quantity=abs(quantity),
            unit_price=abs(unit_price),
            fee=abs(fee),
            currency="TWD",
            executed_at=executed_at,
        )

    def _get_field(
        self, row: dict, field_name: str, default: str | None = ""
    ) -> str:
        """安全取得欄位值"""
        if not field_name:
            return default or ""
        value = row.get(field_name)
        if value is None:
            if default is not None:
                return default
            raise ValueError(f"缺少必要欄位: {field_name}")
        return str(value).strip()

    def _parse_date(self, date_str: str) -> datetime:
        """嘗試多種日期格式解析"""
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y%m%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        # 處理民國年（如 114/01/15）
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3 and len(parts[0]) <= 3:
                try:
                    year = int(parts[0]) + 1911
                    return datetime(year, int(parts[1]), int(parts[2]))
                except (ValueError, IndexError):
                    pass

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        raise ValueError(f"無法解析日期: {date_str}")
