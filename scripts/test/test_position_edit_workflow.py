"""
持倉編輯工作流程測試

驗證修改持倉標的屬性（類別/代號/幣別）時：
1. 該標的所有交易紀錄同步更新
2. 持倉列以新屬性重建（category_id / currency / name 正確傳播）
3. 數量與均價重算正確
4. 改名到既有標的時正確合併
"""

import asyncio
import sys
from datetime import datetime, timedelta
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
    net_worth,
    portfolio,
    position,
    transaction,
    user,
)
from app.models.asset_category import AssetCategory, DEFAULT_CATEGORIES  # noqa: E402
from app.models.portfolio import Portfolio  # noqa: E402
from app.models.position import CurrentPosition  # noqa: E402
from app.models.transaction import Transaction  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.transaction import PositionAssetUpdate, TransactionCreate  # noqa: E402
from app.services.transaction_service import TransactionService  # noqa: E402


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_disable_driver_tx(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _sqlite_emit_begin(conn):
        conn.exec_driver_sql("BEGIN")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # 建立基礎資料
        for cat in DEFAULT_CATEGORIES:
            session.add(AssetCategory(**cat))
        demo_user = User(email="edit-test@example.com", username="edit-test", hashed_password="x")
        session.add(demo_user)
        await session.flush()
        p = Portfolio(user_id=demo_user.id, name="測試組合", base_currency="TWD")
        session.add(p)
        await session.flush()

        service = TransactionService(session)
        base_time = datetime(2026, 1, 5, 10, 0, 0)

        # 情境：誤把台股 0050 建成美股（category 2 / USD）
        for i, (qty, price) in enumerate([(3000, Decimal("40")), (2367, Decimal("46.32"))]):
            await service.create_transaction(TransactionCreate(
                portfolio_id=p.id, category_id=2, symbol="0050",
                asset_name="YUANTA SECURITIES INV TRUST CO",
                tx_type="buy", quantity=Decimal(qty), unit_price=price,
                currency="USD", executed_at=base_time + timedelta(days=i),
            ))
        await session.flush()

        # === 修正為台股 / TWD ===
        pos = await service.update_position_asset(
            p.id, "0050",
            PositionAssetUpdate(category_id=1, currency="TWD", name="元大台灣50"),
        )
        assert pos.category_id == 1, f"category_id 應為 1，實際 {pos.category_id}"
        assert pos.currency == "TWD", f"currency 應為 TWD，實際 {pos.currency}"
        assert pos.name == "元大台灣50"
        assert pos.total_quantity == Decimal("5367")
        # 加權平均: (3000*40 + 2367*46.32) / 5367
        expected_avg = ((Decimal("3000") * Decimal("40") + Decimal("2367") * Decimal("46.32")) / Decimal("5367")).quantize(Decimal("0.00000001"))
        assert pos.avg_cost == expected_avg, f"avg_cost 應為 {expected_avg}，實際 {pos.avg_cost}"

        # 交易紀錄應同步更新
        txs = (await session.execute(
            select(Transaction).where(Transaction.portfolio_id == p.id)
        )).scalars().all()
        assert all(t.category_id == 1 and t.currency == "TWD" for t in txs)
        assert all(t.asset_name == "元大台灣50" for t in txs)
        print("✅ 情境 1：修正市場/幣別/名稱 → 交易與持倉皆正確更新")

        # === 改代號 ===
        pos2 = await service.update_position_asset(
            p.id, "0050", PositionAssetUpdate(symbol="0050.TW"),
        )
        assert pos2.symbol == "0050.TW"
        assert pos2.total_quantity == Decimal("5367")
        assert pos2.category_id == 1 and pos2.currency == "TWD"
        old = (await session.execute(
            select(CurrentPosition).where(CurrentPosition.symbol == "0050")
        )).scalar_one_or_none()
        assert old is None, "舊代號持倉應已刪除"
        print("✅ 情境 2：改代號 → 舊持倉列移除、新代號保留屬性")

        # === 改名合併到既有標的 ===
        await service.create_transaction(TransactionCreate(
            portfolio_id=p.id, category_id=1, symbol="0056",
            asset_name="元大高股息", tx_type="buy",
            quantity=Decimal("1000"), unit_price=Decimal("35"),
            currency="TWD", executed_at=base_time + timedelta(days=10),
        ))
        await session.flush()
        merged = await service.update_position_asset(
            p.id, "0056", PositionAssetUpdate(symbol="0050.TW", name="元大台灣50"),
        )
        assert merged.total_quantity == Decimal("6367"), f"合併後數量應為 6367，實際 {merged.total_quantity}"
        positions = (await session.execute(
            select(CurrentPosition).where(CurrentPosition.portfolio_id == p.id)
        )).scalars().all()
        assert len(positions) == 1, f"合併後應只剩 1 筆持倉，實際 {len(positions)}"
        print("✅ 情境 3：改代號至既有標的 → 正確合併重算")

        # === 不存在的標的應報錯 ===
        try:
            await service.update_position_asset(p.id, "NOPE", PositionAssetUpdate(category_id=1))
            raise AssertionError("應拋出 ValueError")
        except ValueError:
            print("✅ 情境 4：不存在的標的 → 正確拋錯")

        # === 調整數量與成本 ===
        before_txs = len((await session.execute(
            select(Transaction).where(Transaction.portfolio_id == p.id)
        )).scalars().all())
        realized_before = sum(
            t.realized_pnl or Decimal("0")
            for t in (await session.execute(
                select(Transaction).where(Transaction.portfolio_id == p.id)
            )).scalars().all()
        )
        pos5 = await service.update_position_asset(
            p.id, "0050.TW",
            PositionAssetUpdate(total_quantity=Decimal("5000"), avg_cost=Decimal("42.5")),
        )
        assert pos5.total_quantity == Decimal("5000"), f"數量應為 5000，實際 {pos5.total_quantity}"
        assert pos5.avg_cost == Decimal("42.5"), f"均價應為 42.5，實際 {pos5.avg_cost}"
        all_txs = (await session.execute(
            select(Transaction).where(Transaction.portfolio_id == p.id)
        )).scalars().all()
        assert len(all_txs) == before_txs + 2, "應新增 2 筆調整交易（沖銷+重建）"
        realized_after = sum(t.realized_pnl or Decimal("0") for t in all_txs)
        assert realized_after == realized_before, (
            f"調整不應影響已實現損益: {realized_before} → {realized_after}"
        )
        print("✅ 情境 5：調整數量/成本 → 精確達標、損益不變、歷史保留")

        # === 只調整成本（數量不變）===
        pos6 = await service.update_position_asset(
            p.id, "0050.TW", PositionAssetUpdate(avg_cost=Decimal("43")),
        )
        assert pos6.total_quantity == Decimal("5000")
        assert pos6.avg_cost == Decimal("43")
        print("✅ 情境 6：只改成本 → 數量不變、成本精確")

        # === 傳相同值 → 不應產生調整交易 ===
        count_before = len((await session.execute(
            select(Transaction).where(Transaction.portfolio_id == p.id)
        )).scalars().all())
        await service.update_position_asset(
            p.id, "0050.TW",
            PositionAssetUpdate(total_quantity=Decimal("5000"), avg_cost=Decimal("43")),
        )
        count_after = len((await session.execute(
            select(Transaction).where(Transaction.portfolio_id == p.id)
        )).scalars().all())
        assert count_after == count_before, "相同值不應新增調整交易"
        print("✅ 情境 7：值未變 → 不產生多餘調整交易")

    print("\n🎉 全部通過")


if __name__ == "__main__":
    asyncio.run(main())
