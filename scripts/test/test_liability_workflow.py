"""
負債管理工作流程測試

驗證：
1. 建立負債 → 自動建立負債持倉、總負債反映
2. 記錄還款 → 餘額沖減、進度統計正確
3. 還款至餘額歸零 → 自動標記結清
4. 刪除還款紀錄 → 餘額回補、恢復進行中
5. 綁定既有持倉 / 下次繳款日計算
"""

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402,F401
    asset_category,
    dca,
    liability,
    net_worth,
    portfolio,
    position,
    transaction,
    user,
)
from app.models.asset_category import AssetCategory, DEFAULT_CATEGORIES  # noqa: E402
from app.models.liability import PaymentCycle  # noqa: E402
from app.models.portfolio import Portfolio  # noqa: E402
from app.models.position import CurrentPosition  # noqa: E402
from app.models.transaction import Transaction, TransactionType  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.liability import LiabilityCreate, LiabilityUpdate, PaymentCreate  # noqa: E402
from app.schemas.transaction import TransactionCreate  # noqa: E402
from app.services.liability_service import LiabilityService, _add_cycle  # noqa: E402
from app.services.transaction_service import TransactionService  # noqa: E402


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_disable_driver_tx(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None
        # 啟用外鍵檢查，模擬 Postgres 行為（否則刪除順序錯誤不會被抓到）
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine.sync_engine, "begin")
    def _sqlite_emit_begin(conn):
        conn.exec_driver_sql("BEGIN")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        for cat in DEFAULT_CATEGORIES:
            session.add(AssetCategory(**cat))
        demo_user = User(email="li-test@example.com", username="li-test", hashed_password="x")
        session.add(demo_user)
        await session.flush()
        p = Portfolio(user_id=demo_user.id, name="測試組合", base_currency="TWD")
        session.add(p)
        await session.flush()

        service = LiabilityService(session)

        # === 1. 建立負債 ===
        li = await service.create_liability(demo_user.id, LiabilityCreate(
            portfolio_id=p.id, name="車貸",
            principal=Decimal("600000"),
            payment_cycle=PaymentCycle.MONTHLY,
            total_periods=60,
            payment_amount=Decimal("10000"),
            payment_day=5,
            start_date=date(2026, 1, 5),
        ))
        pos = (await session.execute(
            select(CurrentPosition).where(CurrentPosition.symbol == li.symbol)
        )).scalar_one()
        assert pos.total_quantity == Decimal("600000"), "持倉應等於本金"
        resp = await service.get_liability(demo_user.id, li.id)
        assert resp.outstanding_balance == Decimal("600000")
        assert resp.progress_pct == 0.0
        # 起始日=撥款日，第一期於下一週期繳款
        assert resp.next_payment_date == date(2026, 2, 5)
        print("✅ 情境 1：建立負債 → 自動建立持倉、餘額=本金")

        # === 2. 記錄還款 ===
        await service.record_payment(demo_user.id, li.id, PaymentCreate(
            amount=Decimal("10000"), payment_date=date(2026, 1, 5),
        ))
        await service.record_payment(demo_user.id, li.id, PaymentCreate(
            amount=Decimal("10000"), payment_date=date(2026, 2, 5),
        ))
        resp = await service.get_liability(demo_user.id, li.id)
        assert resp.outstanding_balance == Decimal("580000"), f"餘額應為 580000，實際 {resp.outstanding_balance}"
        assert resp.paid_periods == 2
        assert resp.paid_amount == Decimal("20000")
        assert abs(resp.progress_pct - 3.33) < 0.01, f"進度應約 3.33%，實際 {resp.progress_pct}"
        assert resp.next_payment_date == date(2026, 4, 5)
        print("✅ 情境 2：記錄還款 → 餘額沖減、進度/下次繳款日正確")

        # === 3. 還清 → 自動結清 ===
        await service.record_payment(demo_user.id, li.id, PaymentCreate(
            amount=Decimal("580000"), payment_date=date(2026, 3, 5),
            note="提前清償",
        ))
        resp = await service.get_liability(demo_user.id, li.id)
        assert resp.outstanding_balance == Decimal("0")
        assert resp.progress_pct == 100.0
        assert resp.is_active is False, "餘額歸零應自動結清"
        print("✅ 情境 3：餘額歸零 → 自動標記結清")

        # === 4. 刪除還款紀錄 → 餘額回補 ===
        last_payment = resp.payments[-1]
        await service.delete_payment(demo_user.id, li.id, last_payment.id)
        resp = await service.get_liability(demo_user.id, li.id)
        assert resp.outstanding_balance == Decimal("580000"), "刪除還款後餘額應回補"
        assert resp.is_active is True, "應恢復進行中"
        assert resp.paid_periods == 2
        print("✅ 情境 4：刪除還款紀錄 → 餘額回補、恢復進行中")

        # === 5. 綁定既有持倉 ===
        tx_service = TransactionService(session)
        await tx_service.create_transaction(TransactionCreate(
            portfolio_id=p.id, category_id=5, symbol="CARD-A",
            asset_name="信用卡", tx_type=TransactionType.DEPOSIT,
            quantity=Decimal("50000"), unit_price=Decimal("1"),
            currency="TWD", executed_at=datetime.now(timezone.utc),
        ))
        await session.flush()
        li2 = await service.create_liability(demo_user.id, LiabilityCreate(
            portfolio_id=p.id, name="信用卡分期",
            principal=Decimal("50000"),
            payment_cycle=PaymentCycle.MONTHLY,
            total_periods=12,
            payment_amount=Decimal("4300"),
            existing_symbol="CARD-A",
        ))
        assert li2.symbol == "CARD-A"
        resp2 = await service.get_liability(demo_user.id, li2.id)
        assert resp2.outstanding_balance == Decimal("50000")
        # 綁定不應建立新交易
        tx_count = len((await session.execute(
            select(Transaction).where(Transaction.symbol == "CARD-A")
        )).scalars().all())
        assert tx_count == 1, "綁定既有持倉不應新增交易"
        print("✅ 情境 5：綁定既有持倉 → 不重複建立部位")

        # === 6. 週期計算 ===
        assert _add_cycle(date(2026, 1, 31), PaymentCycle.MONTHLY, 1) == date(2026, 2, 28)
        assert _add_cycle(date(2026, 1, 5), PaymentCycle.QUARTERLY, 2) == date(2026, 7, 5)
        assert _add_cycle(date(2026, 1, 5), PaymentCycle.WEEKLY, 3) == date(2026, 1, 26)
        assert _add_cycle(date(2026, 1, 5), PaymentCycle.BIWEEKLY, 2) == date(2026, 2, 2)
        print("✅ 情境 6：週期計算（含月底/跨年）正確")

        # === 7. 依日期自動補登 ===
        li3 = await service.create_liability(demo_user.id, LiabilityCreate(
            portfolio_id=p.id, name="信貸",
            principal=Decimal("120000"),
            payment_cycle=PaymentCycle.MONTHLY,
            total_periods=12,
            payment_amount=Decimal("10000"),
            payment_day=17,
            start_date=date(2025, 1, 17),
        ))
        as_of = date(2025, 6, 20)  # 1/17 撥款 → 第一期 2/17，至 6/20 應已繳 5 期
        preview = await service.preview_backfill(demo_user.id, li3.id, as_of=as_of)
        assert preview.expected_periods == 5, f"應繳 5 期，實際 {preview.expected_periods}"
        assert preview.pending_periods == 5
        assert preview.pending_amount == Decimal("50000")
        assert preview.first_date == date(2025, 2, 17)
        assert preview.last_date == date(2025, 6, 17)

        created = await service.backfill_payments(demo_user.id, li3.id, as_of=as_of)
        assert created == 5, f"應補登 5 期，實際 {created}"
        resp3 = await service.get_liability(demo_user.id, li3.id)
        assert resp3.paid_periods == 5
        assert resp3.outstanding_balance == Decimal("70000")
        assert resp3.next_payment_date == date(2025, 7, 17)
        # 重複執行不應多補
        assert await service.backfill_payments(demo_user.id, li3.id, as_of=as_of) == 0
        print("✅ 情境 7：依日期自動補登 → 期數/金額/下次繳款日正確、重跑冪等")

        # === 8. 補登以餘額為上限、歸零自動結清 ===
        li4 = await service.create_liability(demo_user.id, LiabilityCreate(
            portfolio_id=p.id, name="小額貸",
            principal=Decimal("25000"),
            payment_cycle=PaymentCycle.MONTHLY,
            total_periods=10,
            payment_amount=Decimal("10000"),
            start_date=date(2025, 1, 1),
        ))
        created = await service.backfill_payments(
            demo_user.id, li4.id, as_of=date(2025, 12, 31)
        )
        assert created == 3, f"餘額 25000 只夠補 3 期（最後一期 5000），實際 {created}"
        resp4 = await service.get_liability(demo_user.id, li4.id)
        assert resp4.outstanding_balance == Decimal("0")
        assert resp4.paid_amount == Decimal("25000")
        assert resp4.is_active is False, "餘額歸零應自動結清"
        print("✅ 情境 8：補登以餘額為上限 → 尾期沖到 0 並自動結清")

        # === 9. 清理重複補登（模擬並發請求造成的重複） ===
        import uuid as _uuid
        from app.models.liability import LiabilityPayment  # noqa: E402

        cat_id = await service._liability_category_id()
        src_payments = (await session.execute(
            select(LiabilityPayment).where(LiabilityPayment.liability_id == li3.id)
        )).scalars().all()
        assert len(src_payments) == 5
        for _ in range(2):  # 模擬多按兩次 → 各期多出兩份重複
            for src in src_payments:
                dup_tx = Transaction(
                    id=str(_uuid.uuid4()),
                    portfolio_id=p.id, category_id=cat_id,
                    symbol=li3.symbol, asset_name="信貸",
                    tx_type=TransactionType.WITHDRAW,
                    quantity=src.amount, unit_price=Decimal("1"),
                    fee=Decimal("0"), currency="TWD",
                    executed_at=datetime.combine(
                        src.payment_date, datetime.min.time(), tzinfo=timezone.utc
                    ),
                )
                session.add(dup_tx)
                session.add(LiabilityPayment(
                    liability_id=li3.id, payment_date=src.payment_date,
                    amount=src.amount, transaction_id=dup_tx.id, note=src.note,
                ))
        await session.flush()

        preview = await service.preview_backfill(demo_user.id, li3.id, as_of=as_of)
        assert preview.duplicate_payments == 10, f"應偵測 10 筆重複，實際 {preview.duplicate_payments}"

        removed = await service.dedupe_backfill_payments(demo_user.id, li3.id)
        assert removed == 10, f"應清除 10 筆，實際 {removed}"
        resp3 = await service.get_liability(demo_user.id, li3.id)
        assert resp3.paid_periods == 5, f"清理後應剩 5 期，實際 {resp3.paid_periods}"
        assert resp3.paid_amount == Decimal("50000")
        assert resp3.outstanding_balance == Decimal("70000"), \
            f"重算後餘額應為 70000，實際 {resp3.outstanding_balance}"
        assert resp3.is_active is True
        # 再跑一次應為 no-op
        assert await service.dedupe_backfill_payments(demo_user.id, li3.id) == 0
        print("✅ 情境 9：清理重複補登 → 保留每期一筆、餘額重算正確")

        # === 10. 清理與排程不符的自動補登（如語意調整/修改起始日後的錯位） ===
        stray_tx = Transaction(
            id=str(_uuid.uuid4()),
            portfolio_id=p.id, category_id=cat_id,
            symbol=li3.symbol, asset_name="信貸",
            tx_type=TransactionType.WITHDRAW,
            quantity=Decimal("10000"), unit_price=Decimal("1"),
            fee=Decimal("0"), currency="TWD",
            executed_at=datetime(2025, 1, 17, tzinfo=timezone.utc),
        )
        session.add(stray_tx)
        session.add(LiabilityPayment(
            liability_id=li3.id,
            payment_date=date(2025, 1, 17),  # 不在排程上（排程從 2/17 起）
            amount=Decimal("10000"), transaction_id=stray_tx.id,
            note="自動補登第 1 期",
        ))
        # 手動輸入的還款不受清理影響（即使日期不在排程上）
        manual = await service.record_payment(demo_user.id, li3.id, PaymentCreate(
            amount=Decimal("1000"), payment_date=date(2025, 6, 1), note="手動提前還款",
        ))
        await session.flush()

        preview = await service.preview_backfill(demo_user.id, li3.id, as_of=as_of)
        assert preview.duplicate_payments == 1, f"應偵測 1 筆錯位，實際 {preview.duplicate_payments}"
        removed = await service.dedupe_backfill_payments(demo_user.id, li3.id)
        assert removed == 1
        resp3 = await service.get_liability(demo_user.id, li3.id)
        assert resp3.paid_periods == 6  # 5 筆自動 + 1 筆手動
        assert resp3.paid_amount == Decimal("51000")
        assert resp3.outstanding_balance == Decimal("69000"), \
            f"重算後餘額應為 69000，實際 {resp3.outstanding_balance}"
        assert any(pm.id == manual.id for pm in resp3.payments), "手動還款不應被清除"
        print("✅ 情境 10：清理排程錯位的自動補登 → 手動紀錄保留、餘額重算正確")

        # === 11. 餘額校正（對齊銀行剩餘本金） ===
        before = await service.get_liability(demo_user.id, li3.id)
        assert before.outstanding_balance == Decimal("69000")
        await service.update_liability(demo_user.id, li3.id, LiabilityUpdate(
            outstanding_balance=Decimal("72500"),  # 銀行含息剩餘本金較高
        ))
        after = await service.get_liability(demo_user.id, li3.id)
        assert after.outstanding_balance == Decimal("72500"), \
            f"校正後餘額應為 72500，實際 {after.outstanding_balance}"
        # 還款紀錄與統計不受影響
        assert after.paid_periods == before.paid_periods
        assert after.paid_amount == before.paid_amount
        # 校正為 0 → 結清；再調高 → 恢復進行中
        await service.update_liability(demo_user.id, li3.id, LiabilityUpdate(
            outstanding_balance=Decimal("0"),
        ))
        assert (await service.get_liability(demo_user.id, li3.id)).is_active is False
        await service.update_liability(demo_user.id, li3.id, LiabilityUpdate(
            outstanding_balance=Decimal("72500"),
        ))
        assert (await service.get_liability(demo_user.id, li3.id)).is_active is True
        print("✅ 情境 11：餘額校正 → 對齊指定金額、還款統計不變、結清狀態正確")

        # === 12. 負債部位不產生損益、入帳日=撥款日 ===
        li3_txs = (await session.execute(
            select(Transaction).where(Transaction.symbol == li3.symbol)
        )).scalars().all()
        deposit_tx = next(
            t for t in li3_txs if t.note and t.note.startswith("建立負債")
        )
        assert deposit_tx.executed_at.date() == date(2025, 1, 17), \
            "入帳交易日期應為撥款日"
        # 全量重算後：所有負債交易 realized_pnl=0、平均成本固定 1
        await tx_service.recalculate_position(p.id, li3.symbol)
        li3_txs = (await session.execute(
            select(Transaction).where(Transaction.symbol == li3.symbol)
        )).scalars().all()
        assert all(
            (t.realized_pnl or Decimal("0")) == Decimal("0") for t in li3_txs
        ), "負債交易不應有已實現損益"
        pos3 = (await session.execute(
            select(CurrentPosition).where(CurrentPosition.symbol == li3.symbol)
        )).scalar_one()
        assert pos3.avg_cost == Decimal("1"), f"負債平均成本應為 1，實際 {pos3.avg_cost}"
        assert pos3.total_quantity == Decimal("72500")
        print("✅ 情境 12：負債部位無損益、成本固定 1、入帳日=撥款日")

        # === 13. 舊資料入帳日自動校正（修復歷史淨值走勢） ===
        deposit_tx.executed_at = datetime(2026, 7, 26, tzinfo=timezone.utc)  # 模擬舊版建立
        await session.flush()
        await service.dedupe_backfill_payments(demo_user.id, li3.id)  # 無重複也會觸發校正
        assert deposit_tx.executed_at.date() == date(2025, 1, 17), \
            f"入帳日應校正為撥款日，實際 {deposit_tx.executed_at.date()}"
        print("✅ 情境 13：舊資料入帳日自動校正為撥款日")

    print("\n🎉 全部通過")


if __name__ == "__main__":
    asyncio.run(main())
