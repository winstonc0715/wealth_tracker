"""
定期定額 CSV 解析器

將券商或手動整理的定期定額扣款資料轉成系統內部匯入格式。
欄位名稱採寬鬆比對，方便後續同一份資料反覆匯入更新。
"""

import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.dca import ExecutionStatus, InvestmentType
from app.schemas.dca import DCAImportColumnInfo, DCAImportRecord

logger = logging.getLogger(__name__)


SUPPORTED_DCA_FORMATS = {"standard", "sinopac"}


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "execution_date": (
        "execution_date", "date", "成交日期", "交易日期", "扣款日期",
        "委託日期", "申購日期",
    ),
    "symbol": (
        "symbol", "stock_id", "ticker", "股票代號", "證券代號",
        "標的代碼", "商品代號",
    ),
    "asset_name": (
        "asset_name", "name", "stock_name", "股票名稱", "證券名稱",
        "標的名稱", "商品名稱",
    ),
    "investment_type": (
        "investment_type", "type", "投資方式", "扣款方式", "委託類型",
    ),
    "target_amount": (
        "target_amount", "amount", "每次投資金額", "投資金額",
        "委託金額", "設定金額",
    ),
    "target_shares": (
        "target_shares", "shares", "每次投資股數", "投資股數",
        "委託股數", "設定股數",
    ),
    "execution_days": (
        "execution_days", "execution_day", "扣款日", "扣款日期日",
        "每月扣款日",
    ),
    "actual_price": (
        "actual_price", "price", "成交價格", "成交價", "單價",
        "成交單價",
    ),
    "quantity": (
        "quantity", "成交股數", "股數", "成交數量", "數量",
    ),
    "fee": ("fee", "手續費", "交易手續費"),
    "total_cost": (
        "total_cost", "扣款金額", "成交金額", "總金額",
        "總扣款金額", "淨收付",
    ),
    "currency": ("currency", "幣別", "交易幣別"),
    "status": ("status", "狀態", "入帳狀態"),
    "note": ("note", "備註", "說明"),
    "broker": ("broker", "券商", "來源"),
}


# 欄位中文名稱、是否必填、說明（供前端提示與 API 文件使用）
FIELD_INFO: dict[str, tuple[str, bool, str]] = {
    "execution_date": (
        "扣款/成交日期", True,
        "支援 2026-05-03、2026/05/03、20260503 與民國年 115/05/03。",
    ),
    "symbol": ("標的代碼", True, "股票或 ETF 代碼，例如 2330、0050、AAPL。"),
    "asset_name": ("標的名稱", False, "例如 台積電；用於顯示，可留空。"),
    "investment_type": (
        "投資方式", False,
        "amount（定額）或 shares（定股），也接受中文「定期定額 / 定期定股」；未填預設定額。",
    ),
    "target_amount": (
        "每次投資金額", False,
        "定額模式的每次設定金額；未填時以扣款金額推導。",
    ),
    "target_shares": (
        "每次投資股數", False,
        "定股模式的每次設定股數；未填時以成交股數推導。",
    ),
    "execution_days": (
        "每月扣款日", False,
        "多個日期以逗號分隔（例如 3,16）；未填時以成交日期的「日」推導。",
    ),
    "actual_price": ("成交價格", False, "單股成交價；與股數擇一提供即可推導其餘欄位。"),
    "quantity": ("成交股數", False, "此次實際成交的股數。"),
    "fee": ("手續費", False, "未填視為 0。"),
    "total_cost": ("總扣款金額", False, "含手續費的總金額；未填時自動計算。"),
    "currency": ("幣別", False, "未填預設 TWD。"),
    "status": (
        "狀態", False,
        "pending / confirmed / skipped / failed，或中文「待確認、已確認、已入帳、已跳過、失敗」；"
        "confirmed（已入帳）會建立或更新對應交易。",
    ),
    "note": ("備註", False, "自由文字，會寫入執行紀錄與交易備註。"),
    "broker": ("券商", False, "未填時使用匯入設定中選擇的券商。"),
}


def get_import_column_info() -> list[DCAImportColumnInfo]:
    """取得匯入 CSV 支援欄位、別名與說明（單一資料來源：FIELD_ALIASES）。"""
    columns: list[DCAImportColumnInfo] = []
    for key, aliases in FIELD_ALIASES.items():
        label, required, description = FIELD_INFO.get(key, (key, False, ""))
        columns.append(
            DCAImportColumnInfo(
                key=key,
                label=label,
                required=required,
                aliases=list(aliases),
                description=description,
            )
        )
    return columns


# CSV 範本：標準格式欄位 + 兩列範例資料
TEMPLATE_HEADERS: tuple[str, ...] = (
    "execution_date", "symbol", "asset_name", "investment_type",
    "target_amount", "target_shares", "execution_days",
    "actual_price", "quantity", "fee", "total_cost",
    "currency", "status", "note",
)

TEMPLATE_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "2026-07-03", "2330", "台積電", "amount",
        "3000", "", "3,16",
        "1050", "2", "1", "2101",
        "TWD", "confirmed", "永豐定期定額",
    ),
    (
        "2026-07-16", "0050", "元大台灣50", "amount",
        "2000", "", "3,16",
        "203.5", "9", "1", "1832.5",
        "TWD", "pending", "",
    ),
)


def build_template_csv() -> str:
    """產生匯入範本 CSV 內容（標準格式）。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerows(TEMPLATE_ROWS)
    return buffer.getvalue()


class DCACSVParser:
    """定期定額 CSV 解析器"""

    def __init__(self, broker_format: str = "standard", broker: str = "sinopac"):
        if broker_format not in SUPPORTED_DCA_FORMATS:
            raise ValueError(f"不支援的定期定額匯入格式: {broker_format}")
        self.broker_format = broker_format
        self.broker = broker

    def parse(self, csv_content: str) -> tuple[list[DCAImportRecord], list[str]]:
        """
        解析 CSV 內容。

        回傳：
            (成功解析的匯入紀錄, 錯誤訊息列表)
        """
        records: list[DCAImportRecord] = []
        errors: list[str] = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for row_num, raw_row in enumerate(reader, start=2):
            row = self._normalize_row(raw_row)
            try:
                record = self._parse_row(row)
                record.source_row = row_num
                records.append(record)
            except Exception as e:
                errors.append(f"第 {row_num} 行: {e}")
                logger.warning("DCA CSV 解析第 %d 行失敗: %s", row_num, e)

        return records, errors

    def _parse_row(self, row: dict[str, str]) -> DCAImportRecord:
        """解析單行扣款資料"""
        execution_date = self._parse_date(
            self._get_required(row, "execution_date"),
        )
        symbol = self._get_required(row, "symbol").upper()
        asset_name = self._get_optional(row, "asset_name")
        broker = self._get_optional(row, "broker") or self.broker
        investment_type = self._parse_investment_type(
            self._get_optional(row, "investment_type"),
        )

        target_amount = self._parse_decimal(
            self._get_optional(row, "target_amount"),
        )
        target_shares = self._parse_decimal(
            self._get_optional(row, "target_shares"),
        )
        actual_price = self._parse_decimal(
            self._get_optional(row, "actual_price"),
        )
        quantity = self._parse_decimal(self._get_optional(row, "quantity"))
        fee = self._parse_decimal(self._get_optional(row, "fee")) or Decimal("0")
        total_cost = self._parse_decimal(
            self._get_optional(row, "total_cost"),
        )
        currency = self._get_optional(row, "currency") or "TWD"
        status = self._parse_status(self._get_optional(row, "status"))
        note = self._get_optional(row, "note")

        if target_amount is None and investment_type == InvestmentType.AMOUNT:
            target_amount = total_cost
        if target_shares is None and investment_type == InvestmentType.SHARES:
            target_shares = quantity

        execution_days = self._parse_execution_days(
            self._get_optional(row, "execution_days"),
            execution_date,
        )

        return DCAImportRecord(
            execution_date=execution_date,
            symbol=symbol,
            asset_name=asset_name,
            broker=broker,
            investment_type=investment_type,
            target_amount=target_amount,
            target_shares=target_shares,
            execution_days=execution_days,
            actual_price=actual_price,
            quantity=quantity,
            fee=fee,
            total_cost=total_cost,
            currency=currency,
            status=status,
            note=note,
        )

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, str]:
        """移除 BOM 與欄位空白，降低不同匯出格式造成的解析失敗。"""
        normalized: dict[str, str] = {}
        for key, value in row.items():
            clean_key = str(key or "").replace("\ufeff", "").strip()
            normalized[clean_key] = "" if value is None else str(value).strip()
        return normalized

    def _get_required(self, row: dict[str, str], field: str) -> str:
        value = self._get_optional(row, field)
        if not value:
            aliases = " / ".join(FIELD_ALIASES[field])
            raise ValueError(f"缺少必要欄位: {aliases}")
        return value

    def _get_optional(self, row: dict[str, str], field: str) -> str | None:
        for alias in FIELD_ALIASES[field]:
            if alias in row and row[alias] != "":
                return row[alias]
        return None

    def _parse_date(self, date_str: str) -> date:
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y%m%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3 and len(parts[0]) <= 3:
                try:
                    year = int(parts[0]) + 1911
                    return date(year, int(parts[1]), int(parts[2]))
                except (ValueError, IndexError):
                    pass

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"無法解析日期: {date_str}")

    def _parse_decimal(self, value: str | None) -> Decimal | None:
        if value is None or value == "":
            return None
        clean_value = (
            value.replace(",", "")
            .replace("NT$", "")
            .replace("$", "")
            .replace("元", "")
            .strip()
        )
        try:
            return abs(Decimal(clean_value))
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"數值解析錯誤: {value}") from e

    def _parse_investment_type(
        self, raw_value: str | None,
    ) -> InvestmentType:
        if not raw_value:
            return InvestmentType.AMOUNT
        value = raw_value.strip().lower()
        if value in {"amount", "定額", "金額", "定期定額"}:
            return InvestmentType.AMOUNT
        if value in {"shares", "share", "定股", "股數", "定期定股"}:
            return InvestmentType.SHARES
        raise ValueError(f"無法辨識投資方式: {raw_value}")

    def _parse_execution_days(
        self,
        raw_value: str | None,
        execution_date: date,
    ) -> list[int]:
        if not raw_value:
            return [execution_date.day]
        normalized = raw_value.replace("，", ",").replace("、", ",")
        days = [int(part.strip()) for part in normalized.split(",") if part.strip()]
        if not days:
            return [execution_date.day]
        return days

    def _parse_status(self, raw_value: str | None) -> ExecutionStatus | None:
        if not raw_value:
            return None
        value = raw_value.strip().lower()
        status_map = {
            "pending": ExecutionStatus.PENDING,
            "待確認": ExecutionStatus.PENDING,
            "confirmed": ExecutionStatus.CONFIRMED,
            "已確認": ExecutionStatus.CONFIRMED,
            "已入帳": ExecutionStatus.CONFIRMED,
            "skipped": ExecutionStatus.SKIPPED,
            "已跳過": ExecutionStatus.SKIPPED,
            "failed": ExecutionStatus.FAILED,
            "失敗": ExecutionStatus.FAILED,
        }
        if value not in status_map:
            raise ValueError(f"無法辨識狀態: {raw_value}")
        return status_map[value]
