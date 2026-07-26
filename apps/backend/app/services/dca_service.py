"""
定期定額服務層

處理定期定額計畫的 CRUD、排程執行、確認入帳等業務邏輯。
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dca import (
    DCASchedule, DCAExecution,
    InvestmentType, ExecutionStatus,
)
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction, TransactionType
from app.schemas.dca import (
    DCAScheduleCreate,
    DCAScheduleUpdate,
    DCAExecutionConfirm,
    DCAImportRecord,
    DCAImportResult,
    DCAImportRowDetail,
)
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.services.transaction_service import TransactionService
from app.price.manager import PriceManager

logger = logging.getLogger(__name__)


class DCAService:
    """定期定額業務邏輯"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== 排程 CRUD ====================

    async def create_schedule(
        self, user_id: str, data: DCAScheduleCreate,
    ) -> DCASchedule:
        """
        建立定期定額計畫

        驗證投資組合歸屬後建立排程。
        """
        # 驗證 portfolio 歸屬
        portfolio = await self.db.get(Portfolio, data.portfolio_id)
        if not portfolio or portfolio.user_id != user_id:
            raise ValueError("投資組合不存在或無權限")

        schedule = DCASchedule(
            user_id=user_id,
            portfolio_id=data.portfolio_id,
            symbol=data.symbol,
            asset_name=data.asset_name,
            category_id=data.category_id,
            broker=data.broker,
            investment_type=data.investment_type,
            target_amount=data.target_amount,
            target_shares=data.target_shares,
            fee_discount=data.fee_discount,
            auto_confirm=data.auto_confirm,
        )
        # 使用方法設定 execution_days（序列化為 JSON）
        schedule.set_execution_days(data.execution_days)

        self.db.add(schedule)
        await self.db.flush()
        await self.db.refresh(schedule)
        return schedule

    async def get_user_schedules(
        self, user_id: str,
    ) -> list[DCASchedule]:
        """
        取得用戶所有定期定額計畫

        包含各計畫的待確認執行數量。
        """
        stmt = (
            select(DCASchedule)
            .options(selectinload(DCASchedule.executions))
            .where(DCASchedule.user_id == user_id)
            .order_by(DCASchedule.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_schedule(
        self,
        user_id: str,
        schedule_id: str,
        data: DCAScheduleUpdate,
    ) -> DCASchedule:
        """更新定期定額計畫"""
        schedule = await self._get_user_schedule(user_id, schedule_id)

        update_data = data.model_dump(exclude_unset=True)

        # execution_days 需特殊處理（list → JSON 字串）
        if "execution_days" in update_data:
            schedule.set_execution_days(update_data.pop("execution_days"))

        for key, value in update_data.items():
            setattr(schedule, key, value)

        await self.db.flush()
        await self.db.refresh(schedule)
        return schedule

    async def delete_schedule(
        self, user_id: str, schedule_id: str,
    ) -> None:
        """刪除定期定額計畫（CASCADE 會連帶刪除所有執行紀錄）"""
        schedule = await self._get_user_schedule(user_id, schedule_id)
        await self.db.delete(schedule)
        await self.db.flush()

    async def toggle_schedule(
        self, user_id: str, schedule_id: str,
    ) -> DCASchedule:
        """切換定期定額計畫啟用狀態"""
        schedule = await self._get_user_schedule(user_id, schedule_id)
        schedule.is_active = not schedule.is_active
        await self.db.flush()
        await self.db.refresh(schedule)
        return schedule

    # ==================== 執行紀錄查詢 ====================

    async def get_pending_executions(
        self, user_id: str,
    ) -> list[DCAExecution]:
        """取得用戶所有待確認的執行紀錄（包含 schedule 資訊）"""
        stmt = (
            select(DCAExecution)
            .join(DCASchedule, DCAExecution.schedule_id == DCASchedule.id)
            .options(selectinload(DCAExecution.schedule))
            .where(
                DCASchedule.user_id == user_id,
                DCAExecution.status == ExecutionStatus.PENDING,
            )
            .order_by(DCAExecution.execution_date.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_execution_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DCAExecution], int]:
        """分頁取得用戶的執行歷史"""
        # 計算總數
        count_stmt = (
            select(func.count())
            .select_from(DCAExecution)
            .join(DCASchedule, DCAExecution.schedule_id == DCASchedule.id)
            .where(DCASchedule.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分頁查詢
        offset = (page - 1) * page_size
        stmt = (
            select(DCAExecution)
            .join(DCASchedule, DCAExecution.schedule_id == DCASchedule.id)
            .options(selectinload(DCAExecution.schedule))
            .where(DCASchedule.user_id == user_id)
            .order_by(DCAExecution.execution_date.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        executions = list(result.scalars().all())

        return executions, total

    # ==================== 確認 / 跳過 ====================

    async def confirm_execution(
        self,
        user_id: str,
        execution_id: str,
        data: DCAExecutionConfirm,
    ) -> DCAExecution:
        """
        確認定期定額執行並建立交易紀錄

        1. 驗證歸屬和狀態
        2. 使用 actual_price 或回退至 estimated_price
        3. 建立 Transaction 紀錄
        4. 更新 execution 狀態
        """
        execution = await self._get_user_execution(user_id, execution_id)

        if execution.status != ExecutionStatus.PENDING:
            raise ValueError(
                f"此執行紀錄狀態為 {execution.status.value}，無法確認"
            )

        # 決定使用的成交價；匯入資料可能已帶入 actual_price。
        final_price = (
            data.actual_price
            or execution.actual_price
            or execution.estimated_price
        )
        if not final_price:
            raise ValueError("缺少成交價格，請提供 actual_price")

        schedule = execution.schedule

        if data.actual_price or not execution.quantity:
            # 手動修正價格時重新計算；匯入的確切股數則保留原值。
            quantity, fee, total_cost = self._calculate_execution(
                schedule, final_price,
            )
        else:
            quantity = execution.quantity
            fee = execution.fee or self._calculate_fee(
                quantity * final_price,
                schedule.fee_discount,
            )
            total_cost = execution.total_cost or (
                quantity * final_price + fee
            ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        # 更新執行紀錄
        execution.actual_price = final_price
        execution.quantity = quantity
        execution.fee = fee
        execution.total_cost = total_cost
        if data.note:
            execution.note = data.note

        await self._sync_transaction_from_execution(
            execution=execution,
            currency="TWD",
            note=data.note or execution.note
            or f"定期定額自動買入 ({schedule.broker})",
        )
        execution.status = ExecutionStatus.CONFIRMED
        execution.confirmed_at = datetime.now(timezone.utc)

        await self.db.flush()
        return execution

    async def skip_execution(
        self, user_id: str, execution_id: str,
    ) -> DCAExecution:
        """跳過指定的執行紀錄"""
        execution = await self._get_user_execution(user_id, execution_id)

        if execution.status != ExecutionStatus.PENDING:
            raise ValueError(
                f"此執行紀錄狀態為 {execution.status.value}，無法跳過"
            )

        execution.status = ExecutionStatus.SKIPPED
        await self.db.flush()
        return execution

    # ==================== 匯入 / 後續更新 ====================

    async def import_records(
        self,
        user_id: str,
        portfolio_id: str,
        category_id: int,
        records: list[DCAImportRecord],
        default_broker: str = "sinopac",
        auto_confirm: bool = False,
        collect_details: bool = False,
    ) -> DCAImportResult:
        """
        匯入定期定額扣款資料並支援重複匯入更新。

        同一使用者、投資組合、券商、標的會共用同一個計畫；同一計畫
        與同一天執行紀錄再次匯入時會更新原紀錄。若已建立交易紀錄，
        後續匯入會同步更新交易，避免重複入帳。

        collect_details=True 時會回傳逐列處理明細（供匯入預覽使用）；
        搭配呼叫端 rollback 即可做到 dry-run 試算。
        """
        portfolio = await self.db.get(Portfolio, portfolio_id)
        if not portfolio or portfolio.user_id != user_id:
            raise ValueError("投資組合不存在或無權限")

        stats = {
            "total_rows": len(records),
            "imported": 0,
            "skipped": 0,
            "schedules_created": 0,
            "schedules_updated": 0,
            "executions_created": 0,
            "executions_updated": 0,
            "transactions_created": 0,
            "transactions_updated": 0,
            "errors": [],
        }
        schedule_cache: dict[tuple[str, str, str], DCASchedule] = {}
        details: list[DCAImportRowDetail] = []

        for index, record in enumerate(records, start=2):
            row_num = record.source_row or index
            row_stats = self._empty_import_stats(total_rows=0)
            row_cache = schedule_cache.copy()
            detail: DCAImportRowDetail | None = None
            if collect_details:
                detail = DCAImportRowDetail(
                    row=row_num,
                    symbol=record.symbol,
                    asset_name=record.asset_name,
                    broker=record.broker or default_broker,
                    execution_date=record.execution_date,
                )
            try:
                # 每列使用 SAVEPOINT，避免單列失敗後留下半套 schedule/execution。
                async with self.db.begin_nested():
                    schedule = await self._upsert_import_schedule(
                        user_id=user_id,
                        portfolio_id=portfolio_id,
                        category_id=category_id,
                        record=record,
                        default_broker=default_broker,
                        cache=row_cache,
                        stats=row_stats,
                    )
                    execution, created = await self._upsert_import_execution(
                        schedule=schedule,
                        record=record,
                        auto_confirm=auto_confirm,
                    )
                    if created:
                        row_stats["executions_created"] += 1
                    else:
                        row_stats["executions_updated"] += 1

                    should_confirm = (
                        auto_confirm
                        or record.status == ExecutionStatus.CONFIRMED
                    )
                    if should_confirm:
                        action = await self._sync_transaction_from_execution(
                            execution=execution,
                            currency=record.currency,
                            note=record.note
                            or f"定期定額匯入 ({schedule.broker})",
                        )
                        if action == "created":
                            row_stats["transactions_created"] += 1
                        elif action == "updated":
                            row_stats["transactions_updated"] += 1
                        execution.status = ExecutionStatus.CONFIRMED
                        if not execution.confirmed_at:
                            execution.confirmed_at = datetime.now(timezone.utc)

                self._merge_import_stats(stats, row_stats)
                schedule_cache.update(row_cache)
                stats["imported"] += 1

                if detail is not None:
                    detail.status = "ok"
                    detail.actual_price = execution.actual_price
                    detail.quantity = execution.quantity
                    detail.total_cost = execution.total_cost
                    if row_stats["schedules_created"]:
                        detail.schedule_action = "create"
                    elif row_stats["schedules_updated"]:
                        detail.schedule_action = "update"
                    else:
                        detail.schedule_action = "unchanged"
                    detail.execution_action = (
                        "create" if row_stats["executions_created"] else "update"
                    )
                    if row_stats["transactions_created"]:
                        detail.transaction_action = "create"
                    elif row_stats["transactions_updated"]:
                        detail.transaction_action = "update"
                    else:
                        detail.transaction_action = "none"
                    details.append(detail)
            except Exception as e:
                stats["skipped"] += 1
                error_msg = f"第 {row_num} 行匯入失敗: {e}"
                stats["errors"].append(error_msg)
                logger.warning(error_msg)
                if detail is not None:
                    detail.status = "error"
                    detail.error = str(e)
                    details.append(detail)

        await self.db.flush()
        result = DCAImportResult(**stats)
        result.details = details
        return result

    @staticmethod
    def _empty_import_stats(total_rows: int) -> dict:
        """建立匯入統計容器，供整批與單列匯入共用。"""
        return {
            "total_rows": total_rows,
            "imported": 0,
            "skipped": 0,
            "schedules_created": 0,
            "schedules_updated": 0,
            "executions_created": 0,
            "executions_updated": 0,
            "transactions_created": 0,
            "transactions_updated": 0,
            "errors": [],
        }

    @staticmethod
    def _merge_import_stats(target: dict, source: dict) -> None:
        """合併單列匯入統計到整批統計。"""
        for key, value in source.items():
            if key in {"total_rows", "imported", "skipped", "errors"}:
                continue
            target[key] += value

    async def _upsert_import_schedule(
        self,
        user_id: str,
        portfolio_id: str,
        category_id: int,
        record: DCAImportRecord,
        default_broker: str,
        cache: dict[tuple[str, str, str], DCASchedule],
        stats: dict,
    ) -> DCASchedule:
        """依券商與標的取得或更新定期定額計畫"""
        broker = record.broker or default_broker
        cache_key = (portfolio_id, broker, record.symbol)
        schedule = cache.get(cache_key)

        if not schedule:
            stmt = (
                select(DCASchedule)
                .where(
                    DCASchedule.user_id == user_id,
                    DCASchedule.portfolio_id == portfolio_id,
                    DCASchedule.broker == broker,
                    DCASchedule.symbol == record.symbol,
                )
                .order_by(DCASchedule.created_at.asc())
            )
            result = await self.db.execute(stmt)
            schedule = result.scalars().first()

        target_amount = record.target_amount
        target_shares = record.target_shares
        execution_days = sorted(
            set(record.execution_days or [record.execution_date.day])
        )

        if not schedule:
            schedule = DCASchedule(
                user_id=user_id,
                portfolio_id=portfolio_id,
                symbol=record.symbol,
                asset_name=record.asset_name,
                category_id=category_id,
                broker=broker,
                investment_type=record.investment_type,
                target_amount=target_amount,
                target_shares=target_shares,
                fee_discount=Decimal("0.1"),
                auto_confirm=False,
                is_active=True,
            )
            schedule.set_execution_days(execution_days)
            self.db.add(schedule)
            await self.db.flush()
            stats["schedules_created"] += 1
            cache[cache_key] = schedule
            return schedule

        changed = False
        field_updates = {
            "category_id": category_id,
            "investment_type": record.investment_type,
        }
        if record.asset_name:
            field_updates["asset_name"] = record.asset_name
        if target_amount is not None:
            field_updates["target_amount"] = target_amount
        if target_shares is not None:
            field_updates["target_shares"] = target_shares

        for field_name, value in field_updates.items():
            if getattr(schedule, field_name) != value:
                setattr(schedule, field_name, value)
                changed = True

        merged_days = sorted(set(schedule.get_execution_days()) | set(execution_days))
        if merged_days != schedule.get_execution_days():
            schedule.set_execution_days(merged_days)
            changed = True

        if changed:
            stats["schedules_updated"] += 1
            await self.db.flush()

        cache[cache_key] = schedule
        return schedule

    async def _upsert_import_execution(
        self,
        schedule: DCASchedule,
        record: DCAImportRecord,
        auto_confirm: bool,
    ) -> tuple[DCAExecution, bool]:
        """新增或更新單次扣款執行紀錄"""
        stmt = (
            select(DCAExecution)
            .where(
                DCAExecution.schedule_id == schedule.id,
                DCAExecution.execution_date == record.execution_date,
            )
        )
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()

        actual_price, quantity, fee, total_cost = (
            self._derive_import_execution_values(schedule, record)
        )
        target_status = record.status or (
            ExecutionStatus.CONFIRMED if auto_confirm else ExecutionStatus.PENDING
        )

        created = execution is None
        if created:
            execution = DCAExecution(
                schedule_id=schedule.id,
                execution_date=record.execution_date,
                status=target_status,
            )
            self.db.add(execution)

        execution.estimated_price = actual_price or execution.estimated_price
        execution.actual_price = actual_price or execution.actual_price
        execution.quantity = quantity or execution.quantity
        execution.fee = fee if fee is not None else execution.fee
        execution.total_cost = total_cost or execution.total_cost
        if record.note:
            execution.note = record.note

        # 已確認的紀錄不可因無狀態匯入被降回待確認。
        if execution.status != ExecutionStatus.CONFIRMED:
            execution.status = target_status
        if execution.status == ExecutionStatus.CONFIRMED and not execution.confirmed_at:
            execution.confirmed_at = datetime.now(timezone.utc)

        await self.db.flush()
        return execution, created

    def _derive_import_execution_values(
        self,
        schedule: DCASchedule,
        record: DCAImportRecord,
    ) -> tuple[
        Decimal | None,
        Decimal | None,
        Decimal | None,
        Decimal | None,
    ]:
        """從匯入列推導成交價、股數、手續費與總成本"""
        actual_price = record.actual_price
        quantity = record.quantity
        fee = record.fee
        total_cost = record.total_cost

        if actual_price is None and quantity and total_cost is not None:
            net_amount = total_cost - (fee or Decimal("0"))
            if net_amount > 0:
                actual_price = (net_amount / quantity).quantize(
                    Decimal("0.00000001"), rounding=ROUND_HALF_UP,
                )

        if quantity is None and actual_price:
            quantity, calculated_fee, calculated_total = self._calculate_execution(
                schedule, actual_price,
            )
            fee = fee if fee is not None else calculated_fee
            total_cost = total_cost or calculated_total

        if actual_price and quantity:
            amount = quantity * actual_price
            fee = fee if fee is not None else self._calculate_fee(
                amount, schedule.fee_discount,
            )
            total_cost = total_cost or (amount + fee).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP,
            )

        return actual_price, quantity, fee, total_cost

    async def _sync_transaction_from_execution(
        self,
        execution: DCAExecution,
        currency: str,
        note: str | None = None,
    ) -> str:
        """
        將確認後的 DCA 執行紀錄同步到交易表。

        回傳：
            "created"、"updated" 或 "unchanged"。
        """
        schedule = execution.schedule
        if not schedule:
            schedule = await self.db.get(DCASchedule, execution.schedule_id)
        if not schedule:
            raise ValueError("找不到定期定額計畫")

        final_price = execution.actual_price or execution.estimated_price
        if not final_price or not execution.quantity:
            raise ValueError("缺少成交價或股數，無法建立交易")

        fee = execution.fee or Decimal("0")
        executed_at = datetime.combine(
            execution.execution_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        tx_note = note or execution.note or f"定期定額匯入 ({schedule.broker})"
        tx_service = TransactionService(self.db)

        if execution.transaction_id:
            existing_tx = await self.db.get(Transaction, execution.transaction_id)
            if existing_tx:
                tx_data = TransactionUpdate(
                    category_id=schedule.category_id,
                    symbol=schedule.symbol,
                    asset_name=schedule.asset_name,
                    tx_type=TransactionType.BUY,
                    quantity=execution.quantity,
                    unit_price=final_price,
                    fee=fee,
                    currency=currency,
                    executed_at=executed_at,
                    note=tx_note,
                )
                await tx_service.update_transaction(
                    execution.transaction_id, tx_data,
                )
                return "updated"

        tx_data = TransactionCreate(
            portfolio_id=schedule.portfolio_id,
            category_id=schedule.category_id,
            symbol=schedule.symbol,
            asset_name=schedule.asset_name,
            tx_type=TransactionType.BUY,
            quantity=execution.quantity,
            unit_price=final_price,
            fee=fee,
            currency=currency,
            executed_at=executed_at,
            note=tx_note,
        )
        tx = await tx_service.create_transaction(tx_data)
        execution.transaction_id = tx.id
        return "created"

    # ==================== 排程執行核心 ====================

    async def execute_pending_schedules(self) -> dict:
        """
        排程核心方法：執行今日應扣款的定期定額

        流程：
        1. 取得所有啟用中的 DCASchedule
        2. 檢查今天是否在 execution_days 中
        3. 排除週末（非交易日）
        4. 檢查是否已有今天的 execution（防重複）
        5. 取得收盤價
        6. 計算股數和手續費
        7. 建立 DCAExecution
        8. auto_confirm 的直接建立交易
        """
        today = date.today()
        stats = {
            "date": str(today),
            "checked": 0,
            "created": 0,
            "auto_confirmed": 0,
            "skipped": 0,
            "errors": [],
        }

        # 排除非交易日
        if not self._is_trading_day(today):
            logger.info("今日 %s 非交易日，跳過定期定額排程", today)
            stats["skipped_reason"] = "非交易日"
            return stats

        # 取得所有啟用中的排程
        stmt = (
            select(DCASchedule)
            .options(selectinload(DCASchedule.category))
            .where(DCASchedule.is_active.is_(True))
        )
        result = await self.db.execute(stmt)
        schedules = result.scalars().all()

        stats["checked"] = len(schedules)
        manager = PriceManager()

        try:
            for schedule in schedules:
                try:
                    await self._process_single_schedule(
                        schedule, today, manager, stats,
                    )
                except Exception as e:
                    error_msg = (
                        f"排程 {schedule.id} ({schedule.symbol}) 執行失敗: {e}"
                    )
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
        finally:
            await manager.close()

        return stats

    async def _process_single_schedule(
        self,
        schedule: DCASchedule,
        today: date,
        manager: PriceManager,
        stats: dict,
    ) -> None:
        """處理單一排程的今日執行"""
        # 檢查今天是否在扣款日中
        execution_days = schedule.get_execution_days()
        if today.day not in execution_days:
            return

        # 檢查是否已有今天的 execution（防重複）
        existing_stmt = (
            select(DCAExecution)
            .where(
                DCAExecution.schedule_id == schedule.id,
                DCAExecution.execution_date == today,
            )
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            logger.info(
                "排程 %s (%s) 今日已有執行紀錄，跳過",
                schedule.id, schedule.symbol,
            )
            return

        # 取得收盤價：根據 category 的 slug 決定報價來源
        category_slug = "tw_stock"
        if schedule.category:
            category_slug = schedule.category.slug

        try:
            price_data = await manager.get_price(
                schedule.symbol, category_slug,
            )
            price = price_data.price
        except Exception as e:
            logger.error(
                "取得 %s 報價失敗: %s", schedule.symbol, e,
            )
            stats["errors"].append(
                f"{schedule.symbol} 報價取得失敗: {e}"
            )
            return

        # 計算股數、手續費、總成本
        quantity, fee, total_cost = self._calculate_execution(
            schedule, price,
        )

        # 建立 DCAExecution
        execution = DCAExecution(
            schedule_id=schedule.id,
            execution_date=today,
            status=ExecutionStatus.PENDING,
            estimated_price=price,
            quantity=quantity,
            fee=fee,
            total_cost=total_cost,
        )
        self.db.add(execution)
        await self.db.flush()
        stats["created"] += 1

        logger.info(
            "建立定期定額執行: %s %s x%s @%s (總額: %s)",
            schedule.symbol, schedule.investment_type.value,
            quantity, price, total_cost,
        )

        # 如果設定了自動確認，直接建立交易
        if schedule.auto_confirm:
            try:
                confirm_data = DCAExecutionConfirm(actual_price=price)
                # 暫時把 schedule 掛上去以利 confirm 使用
                execution.schedule = schedule
                await self.confirm_execution(
                    schedule.user_id, execution.id, confirm_data,
                )
                stats["auto_confirmed"] += 1
                logger.info(
                    "自動確認執行: %s %s", schedule.symbol, execution.id,
                )
            except Exception as e:
                error_msg = (
                    f"自動確認 {schedule.symbol} 失敗: {e}"
                )
                logger.error(error_msg)
                stats["errors"].append(error_msg)

    # ==================== 計算輔助方法 ====================

    @staticmethod
    def _calculate_fee(
        amount: Decimal, fee_discount: Decimal,
    ) -> Decimal:
        """
        計算手續費

        台股手續費率 0.1425%，乘以折扣比例。
        最低手續費 1 元。
        """
        base_rate = Decimal("0.001425")  # 0.1425%
        fee = amount * base_rate * fee_discount
        return max(fee, Decimal("1")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _calculate_execution(
        schedule: DCASchedule, price: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        計算單次執行的股數、手續費、總成本

        Returns:
            (quantity, fee, total_cost)
        """
        if schedule.investment_type == InvestmentType.AMOUNT:
            # 定額模式：以目標金額計算整股數量
            raw_shares = schedule.target_amount / price
            # 取整股（向下取整）
            quantity = raw_shares.quantize(
                Decimal("1"), rounding=ROUND_DOWN,
            )
            if quantity <= 0:
                quantity = Decimal("1")  # 至少買一股
            actual_amount = quantity * price
        else:
            # 定股模式：直接使用目標股數
            quantity = schedule.target_shares
            actual_amount = quantity * price

        fee = DCAService._calculate_fee(
            actual_amount, schedule.fee_discount,
        )
        total_cost = (actual_amount + fee).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP,
        )

        return quantity, fee, total_cost

    @staticmethod
    def _is_trading_day(check_date: date) -> bool:
        """
        判斷是否為交易日

        簡單版：排除週六日。
        （未來可擴充國定假日判斷）
        """
        # weekday(): 0=Mon, 5=Sat, 6=Sun
        return check_date.weekday() < 5

    # ==================== 內部輔助方法 ====================

    async def _get_user_schedule(
        self, user_id: str, schedule_id: str,
    ) -> DCASchedule:
        """取得並驗證用戶的排程計畫"""
        schedule = await self.db.get(DCASchedule, schedule_id)
        if not schedule or schedule.user_id != user_id:
            raise ValueError("定期定額計畫不存在或無權限")
        return schedule

    async def _get_user_execution(
        self, user_id: str, execution_id: str,
    ) -> DCAExecution:
        """取得並驗證用戶的執行紀錄"""
        stmt = (
            select(DCAExecution)
            .join(DCASchedule, DCAExecution.schedule_id == DCASchedule.id)
            .options(selectinload(DCAExecution.schedule))
            .where(
                DCAExecution.id == execution_id,
                DCASchedule.user_id == user_id,
            )
        )
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()
        if not execution:
            raise ValueError("執行紀錄不存在或無權限")
        return execution
