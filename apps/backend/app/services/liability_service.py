"""
負債管理服務層

負債主檔 CRUD、還款記錄與進度計算。
負債餘額以 category=liability 的 CurrentPosition 為準（單價固定 1）：
- 建立負債 → 產生 deposit 交易建立持倉
- 記錄還款 → 產生 withdraw 交易沖減持倉
"""

import logging
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset_category import AssetCategory
from app.models.liability import Liability, LiabilityPayment, PaymentCycle
from app.models.position import CurrentPosition
from app.models.transaction import TransactionType
from app.schemas.liability import (
    LiabilityCreate, LiabilityUpdate, PaymentCreate,
    LiabilityResponse, PaymentResponse, BackfillPreview,
)
from app.schemas.transaction import TransactionCreate
from app.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


def _add_cycle(base: date, cycle: PaymentCycle, periods: int) -> date:
    """從 base 起算第 periods 期的日期"""
    if cycle == PaymentCycle.WEEKLY:
        return base + timedelta(weeks=periods)
    if cycle == PaymentCycle.BIWEEKLY:
        return base + timedelta(weeks=2 * periods)

    months = periods * (3 if cycle == PaymentCycle.QUARTERLY else 1)
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    day = min(base.day, monthrange(year, month)[1])
    return date(year, month, day)


def _due_date(liability: Liability, period_index: int) -> date:
    """第 period_index 期（0-based）的應繳日，含每期繳款日調整"""
    due = _add_cycle(
        liability.start_date, liability.payment_cycle, period_index
    )
    if liability.payment_day and liability.payment_cycle in (
        PaymentCycle.MONTHLY, PaymentCycle.QUARTERLY
    ):
        day = min(liability.payment_day, monthrange(due.year, due.month)[1])
        due = due.replace(day=day)
    return due


def _expected_periods(liability: Liability, as_of: date) -> int:
    """依日期推算至 as_of 為止應已繳的期數（上限為總期數）"""
    if not liability.start_date:
        return 0
    count = 0
    while (
        count < liability.total_periods
        and _due_date(liability, count) <= as_of
    ):
        count += 1
    return count


class LiabilityService:
    """負債業務邏輯"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _liability_category_id(self) -> int:
        stmt = select(AssetCategory.id).where(AssetCategory.slug == "liability")
        result = await self.db.execute(stmt)
        cat_id = result.scalar_one_or_none()
        if cat_id is None:
            raise ValueError("找不到負債資產類別")
        return cat_id

    async def _get_position(
        self, portfolio_id: str, symbol: str
    ) -> CurrentPosition | None:
        stmt = (
            select(CurrentPosition)
            .where(CurrentPosition.portfolio_id == portfolio_id)
            .where(CurrentPosition.symbol == symbol)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_liability(
        self, user_id: str, data: LiabilityCreate
    ) -> Liability:
        """建立負債主檔；未綁定既有持倉時自動建立負債持倉"""
        category_id = await self._liability_category_id()

        if data.existing_symbol:
            symbol = data.existing_symbol.upper().strip()
            position = await self._get_position(data.portfolio_id, symbol)
            if not position:
                raise ValueError(f"找不到持倉 {symbol}，無法綁定")
        else:
            symbol = f"DEBT-{uuid.uuid4().hex[:6].upper()}"
            tx_service = TransactionService(self.db)
            await tx_service.create_transaction(TransactionCreate(
                portfolio_id=data.portfolio_id,
                category_id=category_id,
                symbol=symbol,
                asset_name=data.name,
                tx_type=TransactionType.DEPOSIT,
                quantity=data.principal,
                unit_price=Decimal("1"),
                fee=Decimal("0"),
                currency=data.currency,
                executed_at=datetime.now(timezone.utc),
                note=f"建立負債「{data.name}」",
            ))

        liability = Liability(
            user_id=user_id,
            portfolio_id=data.portfolio_id,
            symbol=symbol,
            name=data.name,
            principal=data.principal,
            payment_cycle=data.payment_cycle,
            total_periods=data.total_periods,
            payment_amount=data.payment_amount,
            payment_day=data.payment_day,
            start_date=data.start_date,
            currency=data.currency,
            note=data.note,
        )
        self.db.add(liability)
        await self.db.flush()
        return liability

    async def update_liability(
        self, user_id: str, liability_id: str, data: LiabilityUpdate
    ) -> Liability:
        liability = await self._get_user_liability(user_id, liability_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(liability, key, value)
        await self.db.flush()
        return liability

    async def delete_liability(self, user_id: str, liability_id: str) -> None:
        """刪除負債主檔（保留交易紀錄與持倉）"""
        liability = await self._get_user_liability(user_id, liability_id)
        await self.db.delete(liability)
        await self.db.flush()

    async def record_payment(
        self, user_id: str, liability_id: str, data: PaymentCreate
    ) -> LiabilityPayment:
        """記錄一筆還款：沖減持倉 + 建立還款紀錄"""
        liability = await self._get_user_liability(user_id, liability_id)
        pay_date = data.payment_date or date.today()

        tx_service = TransactionService(self.db)
        tx = await tx_service.create_transaction(TransactionCreate(
            portfolio_id=liability.portfolio_id,
            category_id=await self._liability_category_id(),
            symbol=liability.symbol,
            asset_name=liability.name,
            tx_type=TransactionType.WITHDRAW,
            quantity=data.amount,
            unit_price=Decimal("1"),
            fee=Decimal("0"),
            currency=liability.currency,
            executed_at=datetime.combine(
                pay_date, datetime.min.time(), tzinfo=timezone.utc
            ),
            note=data.note or f"還款「{liability.name}」",
        ))

        payment = LiabilityPayment(
            liability_id=liability.id,
            payment_date=pay_date,
            amount=data.amount,
            transaction_id=tx.id,
            note=data.note,
        )
        self.db.add(payment)
        await self.db.flush()

        # 餘額歸零自動結清
        position = await self._get_position(liability.portfolio_id, liability.symbol)
        if position and position.total_quantity <= 0:
            liability.is_active = False
            logger.info("負債「%s」餘額歸零，自動標記結清", liability.name)

        return payment

    async def delete_payment(
        self, user_id: str, liability_id: str, payment_id: str
    ) -> None:
        """刪除還款紀錄（連同沖減交易一併刪除、重算持倉）"""
        liability = await self._get_user_liability(user_id, liability_id)
        payment = await self.db.get(LiabilityPayment, payment_id)
        if not payment or payment.liability_id != liability.id:
            raise ValueError("還款紀錄不存在")

        tx_service = TransactionService(self.db)
        if payment.transaction_id:
            try:
                await tx_service.delete_transaction(payment.transaction_id)
            except ValueError:
                pass  # 交易已被手動刪除
        await self.db.delete(payment)
        await self.db.flush()

        if not liability.is_active:
            liability.is_active = True

    async def preview_backfill(
        self, user_id: str, liability_id: str, as_of: date | None = None
    ) -> BackfillPreview:
        """預覽依日期推算的待補登期數與金額（不寫入）"""
        liability = await self._get_user_liability(user_id, liability_id)
        as_of = as_of or date.today()
        expected = _expected_periods(liability, as_of)
        paid = len(liability.payments)

        position = await self._get_position(
            liability.portfolio_id, liability.symbol
        )
        remaining = position.total_quantity if position else Decimal("0")
        if remaining < 0:
            remaining = Decimal("0")

        pending_dates: list[date] = []
        pending_amount = Decimal("0")
        for i in range(paid, expected):
            amount = min(liability.payment_amount, remaining)
            if amount <= 0:
                break
            pending_dates.append(_due_date(liability, i))
            pending_amount += amount
            remaining -= amount

        return BackfillPreview(
            expected_periods=expected,
            paid_periods=paid,
            pending_periods=len(pending_dates),
            pending_amount=pending_amount,
            first_date=pending_dates[0] if pending_dates else None,
            last_date=pending_dates[-1] if pending_dates else None,
        )

    async def backfill_payments(
        self, user_id: str, liability_id: str, as_of: date | None = None
    ) -> int:
        """依日期推算補登過往還款：每期建立還款紀錄與沖減交易。

        金額以剩餘餘額為上限，餘額歸零即停（record_payment 會自動結清）。
        重複執行安全：只補「已繳期數」到「應繳期數」之間的缺口。
        """
        liability = await self._get_user_liability(user_id, liability_id)
        as_of = as_of or date.today()
        expected = _expected_periods(liability, as_of)
        paid = len(liability.payments)

        created = 0
        for i in range(paid, expected):
            position = await self._get_position(
                liability.portfolio_id, liability.symbol
            )
            remaining = position.total_quantity if position else Decimal("0")
            amount = min(liability.payment_amount, remaining)
            if amount <= 0:
                break
            await self.record_payment(user_id, liability.id, PaymentCreate(
                amount=amount,
                payment_date=_due_date(liability, i),
                note=f"自動補登第 {i + 1} 期",
            ))
            created += 1

        if created:
            logger.info(
                "負債「%s」自動補登 %d 期還款", liability.name, created
            )
        return created

    async def list_liabilities(
        self, user_id: str, portfolio_id: str
    ) -> list[LiabilityResponse]:
        stmt = (
            select(Liability)
            .where(Liability.user_id == user_id)
            .where(Liability.portfolio_id == portfolio_id)
            .order_by(Liability.created_at.asc())
        )
        result = await self.db.execute(stmt)
        liabilities = result.scalars().all()
        return [await self._to_response(li) for li in liabilities]

    async def get_liability(
        self, user_id: str, liability_id: str
    ) -> LiabilityResponse:
        liability = await self._get_user_liability(user_id, liability_id)
        return await self._to_response(liability)

    async def _to_response(self, liability: Liability) -> LiabilityResponse:
        """組合含進度統計的回應"""
        position = await self._get_position(
            liability.portfolio_id, liability.symbol
        )
        outstanding = (
            position.total_quantity if position else Decimal("0")
        )
        if outstanding < 0:
            outstanding = Decimal("0")

        paid_amount = sum(
            (p.amount for p in liability.payments), Decimal("0")
        )
        paid_periods = len(liability.payments)

        if liability.principal > 0:
            progress = float(
                (liability.principal - outstanding) / liability.principal * 100
            )
            progress = max(0.0, min(100.0, progress))
        else:
            progress = 0.0

        next_payment = None
        if liability.is_active and liability.start_date:
            next_payment = _due_date(liability, paid_periods)

        resp = LiabilityResponse.model_validate(liability)
        resp.outstanding_balance = outstanding
        resp.paid_amount = paid_amount
        resp.paid_periods = paid_periods
        resp.expected_periods = _expected_periods(liability, date.today())
        resp.progress_pct = round(progress, 2)
        resp.next_payment_date = next_payment
        resp.payments = [
            PaymentResponse.model_validate(p) for p in liability.payments
        ]
        return resp

    async def _get_user_liability(
        self, user_id: str, liability_id: str
    ) -> Liability:
        # populate_existing + selectinload：確保 identity map 命中時
        # payments 仍被預載，避免 async session 下的同步 lazy load
        liability = await self.db.get(
            Liability,
            liability_id,
            options=[selectinload(Liability.payments)],
            populate_existing=True,
        )
        if not liability or liability.user_id != user_id:
            raise ValueError("負債不存在")
        return liability
