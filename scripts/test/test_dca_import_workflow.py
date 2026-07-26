"""
定期定額匯入工作流程測試

驗證同一筆扣款資料重複匯入時會更新既有執行紀錄與交易，
而不是建立重複交易。
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.broker.dca_csv_parser import DCACSVParser  # noqa: E402
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
from app.models.asset_category import AssetCategory  # noqa: E402
from app.models.dca import DCAExecution  # noqa: E402
from app.models.dca import DCASchedule  # noqa: E402
from app.models.portfolio import Portfolio  # noqa: E402
from app.models.transaction import Transaction  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.dca_service import DCAService  # noqa: E402


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    parser = DCACSVParser(broker_format="standard", broker="sinopac")

    async with session_factory() as session:
        demo_user = User(
            email="dca-import@example.com",
            username="dca_import",
            hashed_password="test",
        )
        session.add(demo_user)
        await session.flush()

        category = AssetCategory(id=1, name="台股", slug="tw_stock")
        portfolio_obj = Portfolio(user_id=demo_user.id, name="長期投資")
        session.add_all([category, portfolio_obj])
        await session.flush()

        first_csv = "\n".join([
            "execution_date,symbol,name,investment_type,target_amount,actual_price,quantity,fee,total_cost,status,note",
            "2026-05-03,2330,台積電,amount,3000,600,5,1,3001,confirmed,初次匯入",
        ])
        first_records, first_errors = parser.parse(first_csv)
        assert not first_errors

        service = DCAService(session)
        first_result = await service.import_records(
            user_id=demo_user.id,
            portfolio_id=portfolio_obj.id,
            category_id=1,
            records=first_records,
            default_broker="sinopac",
            auto_confirm=True,
        )
        assert first_result.imported == 1
        assert first_result.executions_created == 1
        assert first_result.transactions_created == 1

        second_csv = "\n".join([
            "execution_date,symbol,name,investment_type,target_amount,actual_price,quantity,fee,total_cost,status,note",
            "2026-05-03,2330,台積電,amount,3000,610,5,2,3052,confirmed,後續更新",
        ])
        second_records, second_errors = parser.parse(second_csv)
        assert not second_errors

        second_result = await service.import_records(
            user_id=demo_user.id,
            portfolio_id=portfolio_obj.id,
            category_id=1,
            records=second_records,
            default_broker="sinopac",
            auto_confirm=True,
        )
        assert second_result.imported == 1
        assert second_result.executions_updated == 1
        assert second_result.transactions_updated == 1

        tx_count = await session.scalar(select(func.count()).select_from(Transaction))
        execution_count = await session.scalar(
            select(func.count()).select_from(DCAExecution)
        )
        tx = await session.scalar(select(Transaction))
        execution = await session.scalar(select(DCAExecution))

        assert tx_count == 1
        assert execution_count == 1
        assert tx is not None
        assert execution is not None
        assert tx.unit_price == Decimal("610")
        assert tx.fee == Decimal("2")
        assert execution.actual_price == Decimal("610")
        assert execution.total_cost == Decimal("3052")

        multi_day_csv = "\n".join([
            "execution_date,symbol,name,investment_type,target_amount,actual_price,quantity,fee,total_cost,status,note",
            "2026-05-16,2330,台積電,amount,3000,620,4,1,2481,pending,第二扣款日",
        ])
        multi_day_records, multi_day_errors = parser.parse(multi_day_csv)
        assert not multi_day_errors
        multi_day_result = await service.import_records(
            user_id=demo_user.id,
            portfolio_id=portfolio_obj.id,
            category_id=1,
            records=multi_day_records,
            default_broker="sinopac",
            auto_confirm=False,
        )
        assert multi_day_result.executions_created == 1
        schedule = await session.scalar(select(DCASchedule))
        assert schedule is not None
        assert schedule.get_execution_days() == [3, 16]

        broken_csv = "\n".join([
            "execution_date,symbol,name,investment_type,target_amount,status,note",
            "2026-05-20,0050,元大台灣50,amount,1000,confirmed,缺成交資料",
        ])
        broken_records, broken_errors = parser.parse(broken_csv)
        assert not broken_errors
        broken_result = await service.import_records(
            user_id=demo_user.id,
            portfolio_id=portfolio_obj.id,
            category_id=1,
            records=broken_records,
            default_broker="sinopac",
            auto_confirm=True,
        )
        assert broken_result.imported == 0
        assert broken_result.skipped == 1
        broken_schedule = await session.scalar(
            select(DCASchedule).where(DCASchedule.symbol == "0050")
        )
        assert broken_schedule is None

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
