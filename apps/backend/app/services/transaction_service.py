"""
交易服務層

處理新增交易、自動更新持倉部位等業務邏輯。
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.models.position import CurrentPosition
from app.models.net_worth import HistoricalNetWorth
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

        # 更新持倉部位並計算損益
        await self._update_position(tx)

        await self.db.flush()

        # 清除受影響日期之後的快照，確保走勢圖重算
        await self._invalidate_snapshots(data.portfolio_id, tx.executed_at.date())

        return tx

    async def update_transaction(
        self, tx_id: str, data: "TransactionUpdate"
    ) -> Transaction:
        """更新交易紀錄並重新計算該標的之所有歷史部位與損益"""
        tx = await self.db.get(Transaction, tx_id)
        if not tx:
            raise ValueError("交易紀錄不存在")

        old_symbol = tx.symbol
        old_portfolio_id = tx.portfolio_id

        # 更新欄位
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(tx, key, value)

        await self.db.flush()

        # 重新計算該標的之損益（如果 symbol 改變了，則需要重新計算兩個標的）
        await self.recalculate_position(old_portfolio_id, old_symbol)
        if tx.symbol != old_symbol:
            await self.recalculate_position(tx.portfolio_id, tx.symbol)

        # 清除受影響日期之後的快照，確保走勢圖重算
        await self._invalidate_snapshots(tx.portfolio_id, tx.executed_at.date())

        return tx

    async def delete_transaction(self, tx_id: str) -> None:
        """刪除交易紀錄並重新計算該標的之所有歷史部位與損益"""
        tx = await self.db.get(Transaction, tx_id)
        if not tx:
            raise ValueError("交易紀錄不存在")

        portfolio_id = tx.portfolio_id
        symbol = tx.symbol
        executed_date = tx.executed_at.date()

        await self.db.delete(tx)
        await self.db.flush()

        # 重新計算該標的之損益
        await self.recalculate_position(portfolio_id, symbol)

        # 清除受影響日期之後的快照，確保走勢圖重算
        await self._invalidate_snapshots(portfolio_id, executed_date)

    async def recalculate_position(self, portfolio_id: str, symbol: str) -> None:
        """
        全量重新計算特定標的之持倉成本與每筆賣出之實現損益
        """
        # 1. 取得該標的所有歷史交易（按執行時間排序）
        stmt = (
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .where(Transaction.symbol == symbol)
            .order_by(Transaction.executed_at.asc(), Transaction.created_at.asc())
        )
        result = await self.db.execute(stmt)
        txs = result.scalars().all()

        # 2. 取得或初始化持倉
        stmt_pos = (
            select(CurrentPosition)
            .where(CurrentPosition.portfolio_id == portfolio_id)
            .where(CurrentPosition.symbol == symbol)
        )
        result_pos = await self.db.execute(stmt_pos)
        position = result_pos.scalar_one_or_none()

        if not txs:
            if position:
                await self.db.delete(position)
            return

        # 3. 循序計算
        current_qty = Decimal("0")
        current_avg_cost = Decimal("0")
        
        # 紀錄第一個交易的 category_id 做為持倉預設
        category_id = txs[0].category_id
        asset_name = txs[0].asset_name
        currency = txs[0].currency

        for tx in txs:
            if tx.tx_type in (TransactionType.BUY, TransactionType.DEPOSIT):
                # 新增成本
                old_total = current_qty * current_avg_cost
                new_total = tx.quantity * tx.unit_price
                current_qty += tx.quantity
                if current_qty > 0:
                    current_avg_cost = (
                        (old_total + new_total) / current_qty
                    ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
                tx.realized_pnl = Decimal("0") # 買入無實現損益
            
            elif tx.tx_type in (TransactionType.SELL, TransactionType.WITHDRAW):
                # 賣出計算損益：(賣價 - 成本) * 數量 - 手續費
                realized = (tx.unit_price - current_avg_cost) * tx.quantity - tx.fee
                tx.realized_pnl = realized.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                current_qty -= tx.quantity
            
            elif tx.tx_type == TransactionType.DIVIDEND:
                # 配息全額為損益
                realized = (tx.unit_price * tx.quantity) - tx.fee
                tx.realized_pnl = realized.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        # 4. 更新持倉模型
        if not position:
            position = CurrentPosition(
                portfolio_id=portfolio_id,
                symbol=symbol,
                category_id=category_id,
                name=asset_name,
                currency=currency,
            )
            self.db.add(position)
        
        position.total_quantity = current_qty
        position.avg_cost = current_avg_cost
        position.updated_at = func.now()

    async def recalculate_all_portfolios(self) -> dict:
        """
        遍歷所有投資組合與標的，重新計算所有損益（強修復模式）
        """
        from app.models.portfolio import Portfolio
        
        # 取得所有 Portfolios
        stmt = select(Portfolio)
        result = await self.db.execute(stmt)
        portfolios = result.scalars().all()
        
        recalculated_count = 0
        for p in portfolios:
            # 取得該投資組合下所有的標的 (Symbols)
            stmt_sym = (
                select(Transaction.symbol)
                .where(Transaction.portfolio_id == p.id)
                .distinct()
            )
            res_sym = await self.db.execute(stmt_sym)
            symbols = res_sym.scalars().all()
            
            for symbol in symbols:
                await self.recalculate_position(p.id, symbol)
                recalculated_count += 1
                
        return {"portfolios": len(portfolios), "symbols": recalculated_count}

    async def _invalidate_snapshots(self, portfolio_id: str, from_date) -> None:
        """清除從 from_date 開始的所有快照，強制下次請求時重算"""
        from datetime import date as date_type
        if not isinstance(from_date, date_type):
            from_date = from_date.date() if hasattr(from_date, 'date') else from_date

        stmt = delete(HistoricalNetWorth).where(
            HistoricalNetWorth.portfolio_id == portfolio_id,
            HistoricalNetWorth.snapshot_date >= from_date,
        )
        result = await self.db.execute(stmt)
        logger.info(
            "已清除 %s 自 %s 起的 %d 筆快照",
            portfolio_id, from_date, result.rowcount
        )

    async def _update_position(self, tx: Transaction) -> None:
        """根據交易類型更新持倉並計算已實現損益"""
        # 查詢現有持倉
        stmt = (
            select(CurrentPosition)
            .where(CurrentPosition.portfolio_id == tx.portfolio_id)
            .where(CurrentPosition.symbol == tx.symbol)
        )
        result = await self.db.execute(stmt)
        position = result.scalar_one_or_none()

        if tx.tx_type in (TransactionType.BUY, TransactionType.DEPOSIT):
            if position:
                # 計算新的加權平均成本
                old_total = position.total_quantity * position.avg_cost
                new_total = tx.quantity * tx.unit_price
                new_quantity = position.total_quantity + tx.quantity

                if new_quantity > 0:
                    position.avg_cost = (
                        (old_total + new_total) / new_quantity
                    ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
                    position.total_quantity = new_quantity
                    # 更新名稱（如果有提供）
                    if tx.asset_name:
                        position.name = tx.asset_name
            else:
                # 建立新持倉
                position = CurrentPosition(
                    portfolio_id=tx.portfolio_id,
                    category_id=tx.category_id,
                    symbol=tx.symbol,
                    name=tx.asset_name,
                    total_quantity=tx.quantity,
                    avg_cost=tx.unit_price,
                    currency=tx.currency,
                )
                self.db.add(position)

        elif tx.tx_type in (TransactionType.SELL, TransactionType.WITHDRAW):
            if not position:
                logger.warning(
                    "賣出 %s 但無持倉記錄，將建立負數持倉", tx.symbol
                )
                position = CurrentPosition(
                    portfolio_id=tx.portfolio_id,
                    category_id=tx.category_id,
                    symbol=tx.symbol,
                    name=tx.asset_name,
                    total_quantity=-tx.quantity,
                    avg_cost=tx.unit_price,
                    currency=tx.currency,
                )
                self.db.add(position)
            else:
                # 賣出計算實現損益：(賣價 - 成本) * 數量 - 手續費
                # 注意：這裡假設賣出不影響平均成本
                realized = (tx.unit_price - position.avg_cost) * tx.quantity - tx.fee
                tx.realized_pnl = realized.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                
                # 減少數量
                position.total_quantity -= tx.quantity

        elif tx.tx_type == TransactionType.DIVIDEND:
            # 配息視為 100% 實現損益：(單價*數量) - 手續費
            realized = (tx.unit_price * tx.quantity) - tx.fee
            tx.realized_pnl = realized.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            
            logger.info(
                "配息入帳 (已實現損益): %s %s, realized=%s",
                tx.symbol, tx.total_amount, tx.realized_pnl
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
