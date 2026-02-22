"""
交易服務層

處理新增交易、自動更新持倉部位等業務邏輯。
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.models.position import CurrentPosition
from app.schemas.transaction import TransactionCreate

logger = logging.getLogger(__name__)


class TransactionService:
    """交易業務邏輯"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transaction(
        self, data: TransactionCreate
    ) -> Transaction:
        """
        新增交易並自動更新持倉部位

        流程：
        1. 建立 Transaction 記錄
        2. 根據交易類型更新 CurrentPosition
           - BUY / DEPOSIT：增加數量，重算平均成本
           - SELL / WITHDRAW：減少數量
           - DIVIDEND：增加法幣部位（或記錄到備註）
        """
        # 建立交易記錄
        tx = Transaction(
            portfolio_id=data.portfolio_id,
            category_id=data.category_id,
            symbol=data.symbol,
            asset_name=data.asset_name,
            tx_type=data.tx_type,
            quantity=data.quantity,
            unit_price=data.unit_price,
            fee=data.fee,
            currency=data.currency,
            executed_at=data.executed_at,
            note=data.note,
        )
        self.db.add(tx)

        # 更新持倉部位
        await self._update_position(data)

        await self.db.flush()
        return tx

    async def _update_position(self, data: TransactionCreate) -> None:
        """根據交易類型更新持倉"""
        # 查詢現有持倉
        stmt = (
            select(CurrentPosition)
            .where(CurrentPosition.portfolio_id == data.portfolio_id)
            .where(CurrentPosition.symbol == data.symbol)
        )
        result = await self.db.execute(stmt)
        position = result.scalar_one_or_none()

        if data.tx_type in (TransactionType.BUY, TransactionType.DEPOSIT):
            if position:
                # 計算新的加權平均成本
                # new_avg = (old_qty × old_avg + new_qty × new_price) / (old_qty + new_qty)
                old_total = position.total_quantity * position.avg_cost
                new_total = data.quantity * data.unit_price
                new_quantity = position.total_quantity + data.quantity

                if new_quantity > 0:
                    position.avg_cost = (
                        (old_total + new_total) / new_quantity
                    ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
                    position.total_quantity = new_quantity
                    # 更新名稱（如果有提供）
                    if data.asset_name:
                        position.name = data.asset_name
            else:
                # 建立新持倉
                position = CurrentPosition(
                    portfolio_id=data.portfolio_id,
                    category_id=data.category_id,
                    symbol=data.symbol,
                    name=data.asset_name,
                    total_quantity=data.quantity,
                    avg_cost=data.unit_price,
                    currency=data.currency,
                )
                self.db.add(position)

        elif data.tx_type in (TransactionType.SELL, TransactionType.WITHDRAW):
            if not position:
                logger.warning(
                    "賣出 %s 但無持倉記錄，將建立負數持倉", data.symbol
                )
                position = CurrentPosition(
                    portfolio_id=data.portfolio_id,
                    category_id=data.category_id,
                    symbol=data.symbol,
                    name=data.asset_name,
                    total_quantity=-data.quantity,
                    avg_cost=data.unit_price,
                    currency=data.currency,
                )
                self.db.add(position)
            else:
                # 賣出不影響平均成本，只減少數量
                position.total_quantity -= data.quantity

        elif data.tx_type == TransactionType.DIVIDEND:
            # 配息：可選擇增加法幣部位或僅記錄
            logger.info(
                "配息入帳: %s %s × %s",
                data.symbol, data.quantity, data.unit_price,
            )

    async def get_transactions(
        self,
        portfolio_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Transaction], int]:
        """取得投資組合的交易紀錄（分頁）"""
        # 計算總數
        from sqlalchemy import func
        count_stmt = (
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 查詢分頁資料
        offset = (page - 1) * page_size
        stmt = (
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()

        return list(transactions), total
