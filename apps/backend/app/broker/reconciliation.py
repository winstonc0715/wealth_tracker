"""
部位比對邏輯 (Reconciliation)

將外部匯入的部位資料與系統內持倉進行比對與校正。
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position import CurrentPosition
from app.schemas.transaction import ReconciliationItem, ReconciliationResult

logger = logging.getLogger(__name__)


class ReconciliationService:
    """部位比對服務"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconcile(
        self,
        portfolio_id: str,
        external_positions: dict[str, Decimal],
    ) -> ReconciliationResult:
        """
        比對外部部位與系統內持倉

        Args:
            portfolio_id: 投資組合 ID
            external_positions: 外部持倉 {symbol: quantity}

        Returns:
            比對結果
        """
        # 查詢系統內持倉
        stmt = (
            select(CurrentPosition)
            .where(CurrentPosition.portfolio_id == portfolio_id)
        )
        result = await self.db.execute(stmt)
        system_positions = {
            p.symbol: p.total_quantity
            for p in result.scalars().all()
        }

        items: list[ReconciliationItem] = []
        all_symbols = set(system_positions.keys()) | set(external_positions.keys())
        matched = 0
        mismatched = 0

        for symbol in sorted(all_symbols):
            sys_qty = system_positions.get(symbol, Decimal("0"))
            ext_qty = external_positions.get(symbol, Decimal("0"))
            diff = ext_qty - sys_qty

            if symbol not in system_positions:
                status = "missing_in_system"
                mismatched += 1
            elif symbol not in external_positions:
                status = "missing_in_external"
                mismatched += 1
            elif abs(diff) < Decimal("0.0001"):
                status = "matched"
                matched += 1
            else:
                status = "mismatch"
                mismatched += 1

            items.append(ReconciliationItem(
                symbol=symbol,
                system_quantity=sys_qty,
                external_quantity=ext_qty,
                difference=diff,
                status=status,
            ))

        return ReconciliationResult(
            portfolio_id=portfolio_id,
            total_symbols=len(all_symbols),
            matched=matched,
            mismatched=mismatched,
            items=items,
        )
