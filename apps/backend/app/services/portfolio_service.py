"""
投資組合服務層

實作淨值計算、資產配置分析等核心業務邏輯。
"""

import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio
from app.models.position import CurrentPosition
from app.models.asset_category import AssetCategory
from app.models.net_worth import HistoricalNetWorth
from app.price.manager import PriceManager
from app.schemas.portfolio import (
    PortfolioSummary, PositionDetail,
    AllocationItem, AllocationResponse,
    PortfolioHistoryResponse, NetWorthHistoryItem,
)

logger = logging.getLogger(__name__)

# 圓餅圖各類別預設顏色
CATEGORY_COLORS: dict[str, str] = {
    "tw_stock": "#3b82f6",     # 藍色
    "us_stock": "#8b5cf6",     # 紫色
    "crypto": "#f59e0b",       # 琥珀色
    "fiat": "#22c55e",         # 綠色
    "liability": "#ef4444",    # 紅色
}


class PortfolioService:
    """投資組合業務邏輯"""

    def __init__(self, db: AsyncSession, price_manager: PriceManager):
        self.db = db
        self.price_manager = price_manager

    async def get_summary(self, portfolio_id: str, force_refresh: bool = False) -> PortfolioSummary:
        """
        計算投資組合淨值摘要

        邏輯：
        1. 查詢所有持倉部位
        2. 對每個部位取得即時報價
        3. 計算總資產、總負債、淨值、未實現損益
        """
        # 取得投資組合
        portfolio = await self.db.get(Portfolio, portfolio_id)
        if not portfolio:
            raise ValueError(f"投資組合 {portfolio_id} 不存在")

        # 取得所有持倉 (僅顯示數量 > 0 的部位)
        stmt = (
            select(CurrentPosition)
            .where(CurrentPosition.portfolio_id == portfolio_id)
            .where(CurrentPosition.total_quantity != 0)
        )
        result = await self.db.execute(stmt)
        positions = result.scalars().all()

        # 取得累計已實現損益 (加總所有交易的 realized_pnl)
        from app.models.transaction import Transaction
        from sqlalchemy import func
        pnl_stmt = (
            select(func.sum(Transaction.realized_pnl))
            .where(Transaction.portfolio_id == portfolio_id)
        )
        pnl_result = await self.db.execute(pnl_stmt)
        total_realized_pnl = pnl_result.scalar() or Decimal("0")

        # 取得 USD 匯率以統一轉為 TWD 計算
        usd_twd_rate = Decimal("32.0")
        try:
            rate_data = await self.price_manager.get_price("TWD=X", "us_stock", force_refresh=force_refresh)
            if rate_data.price > 0:
                usd_twd_rate = rate_data.price
        except Exception as e:
            logger.warning("取得匯率失敗，使用預設值 32.0: %s", e)

        # 批次取得報價
        price_items = [
            (p.symbol, p.category.slug if p.category else "fiat")
            for p in positions
        ]
        prices = await self.price_manager.get_prices_batch(price_items, force_refresh=force_refresh)

        # 計算各項指標
        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        total_unrealized_pnl = Decimal("0")
        position_details: list[PositionDetail] = []

        for pos in positions:
            category_slug = pos.category.slug if pos.category else "fiat"
            price_data = prices.get(pos.symbol)
            current_price = price_data.price if price_data else Decimal("0")
            avg_cost = pos.avg_cost

            # 原幣計算 (Native currency calculation)
            total_value_native = (pos.total_quantity * current_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            total_cost_native = (pos.total_quantity * avg_cost).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            unrealized_pnl_native = total_value_native - total_cost_native
            pnl_pct = (
                (unrealized_pnl_native / total_cost_native * 100)
                if total_cost_native > 0
                else Decimal("0")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # TWD 等值計算 (用於總資產、淨值加總)
            twd_multiplier = usd_twd_rate if category_slug in ("us_stock", "crypto") else Decimal("1")
            total_value_twd = total_value_native * twd_multiplier
            unrealized_pnl_twd = unrealized_pnl_native * twd_multiplier

            # 區分資產與負債加總 (使用 TWD 價值)
            if category_slug == "liability":
                total_liabilities += total_value_twd
            else:
                total_assets += total_value_twd

            total_unrealized_pnl += unrealized_pnl_twd

            # 明細保留原幣顯示 (供前端顯示)
            position_details.append(PositionDetail(
                symbol=pos.symbol,
                name=pos.name,
                category_slug=category_slug,
                total_quantity=pos.total_quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                total_value=total_value_native,
                total_cost=total_cost_native,
                unrealized_pnl=unrealized_pnl_native,
                unrealized_pnl_pct=pnl_pct,
                currency=pos.currency if pos.currency else ("USD" if category_slug in ("us_stock", "crypto") else "TWD"),
            ))

        net_worth = total_assets - total_liabilities

        return PortfolioSummary(
            portfolio_id=portfolio_id,
            portfolio_name=portfolio.name,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_worth=net_worth,
            total_unrealized_pnl=total_unrealized_pnl,
            total_realized_pnl=total_realized_pnl,
            positions=position_details,
            last_updated=datetime.now(),
        )

    async def get_allocations(self, portfolio_id: str, force_refresh: bool = False) -> AllocationResponse:
        """
        計算資產配置比例（圓餅圖用）

        依照 asset_category 分組，計算各類別佔總資產的百分比。
        """
        summary = await self.get_summary(portfolio_id, force_refresh)

        # 取得 USD 匯率以統一轉為 TWD 計算
        usd_twd_rate = Decimal("32.0")
        try:
            rate_data = await self.price_manager.get_price("TWD=X", "us_stock", force_refresh=force_refresh)
            if rate_data.price > 0:
                usd_twd_rate = rate_data.price
        except Exception as e:
            logger.warning("取得匯率失敗，使用預設值 32.0: %s", e)

        # 按類別聚合
        category_values: dict[str, Decimal] = {}
        category_names: dict[str, str] = {}

        for pos in summary.positions:
            if pos.category_slug == "liability":
                continue  # 負債不計入配置
            slug = pos.category_slug
            
            # 使用 TWD 價值來加總比例
            twd_multiplier = usd_twd_rate if slug in ("us_stock", "crypto") else Decimal("1")
            value_twd = pos.total_value * twd_multiplier
            
            category_values[slug] = category_values.get(slug, Decimal("0")) + value_twd

            # 取得類別中文名
            if slug not in category_names:
                stmt = select(AssetCategory).where(AssetCategory.slug == slug)
                result = await self.db.execute(stmt)
                cat = result.scalar_one_or_none()
                category_names[slug] = cat.name if cat else slug

        total = sum(category_values.values())
        allocations = []

        for slug, value in category_values.items():
            pct = (
                (value / total * 100) if total > 0 else Decimal("0")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            allocations.append(AllocationItem(
                category=category_names.get(slug, slug),
                category_slug=slug,
                value=value,
                percentage=pct,
                color=CATEGORY_COLORS.get(slug),
            ))

        return AllocationResponse(
            portfolio_id=portfolio_id,
            total_value=total,
            allocations=allocations,
        )

    async def save_net_worth_snapshot(self, portfolio_id: str) -> HistoricalNetWorth:
        """
        儲存每日淨值快照（供排程呼叫）
        """
        from datetime import date as date_type

        summary = await self.get_summary(portfolio_id)
        today = date_type.today()

        # 查詢是否已有今日快照
        stmt = (
            select(HistoricalNetWorth)
            .where(HistoricalNetWorth.portfolio_id == portfolio_id)
            .where(HistoricalNetWorth.snapshot_date == today)
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        # 建立 breakdown JSON
        breakdown = {}
        for pos in summary.positions:
            slug = pos.category_slug
            if slug not in breakdown:
                breakdown[slug] = {"total": "0", "items": []}
            breakdown[slug]["items"].append({
                "symbol": pos.symbol,
                "value": str(pos.total_value),
            })
            current = Decimal(breakdown[slug]["total"])
            breakdown[slug]["total"] = str(current + pos.total_value)

        if existing:
            # 更新既有快照
            existing.total_assets = summary.total_assets
            existing.total_liabilities = summary.total_liabilities
            existing.net_worth = summary.net_worth
            existing.breakdown = breakdown
            return existing
        else:
            # 建立新快照
            snapshot = HistoricalNetWorth(
                portfolio_id=portfolio_id,
                snapshot_date=today,
                total_assets=summary.total_assets,
                total_liabilities=summary.total_liabilities,
                net_worth=summary.net_worth,
                breakdown=breakdown,
            )
            self.db.add(snapshot)
            return snapshot

    async def get_history(self, portfolio_id: str, days: int = 30, force_refresh: bool = False) -> PortfolioHistoryResponse:
        """
        取得投資組合歷史淨值走勢（供走勢圖使用）
        
        若 HistoricalNetWorth 快照充足則直接使用；否則啟動「歷史淨值回溯引擎」，
        將過去所有交易紀錄逐日回放，並乘上當天個股的真實歷史收盤價，精確還原歷史波段。
        """
        from datetime import date, timedelta
        from sqlalchemy.orm import selectinload
        from app.models.transaction import Transaction
        from app.models.asset_category import AssetCategory

        today = date.today()
        start_date = today - timedelta(days=days-1)

        # 1. 取得歷史快照
        stmt = (
            select(HistoricalNetWorth)
            .where(HistoricalNetWorth.portfolio_id == portfolio_id)
            .where(HistoricalNetWorth.snapshot_date >= start_date)
            .order_by(HistoricalNetWorth.snapshot_date.asc())
        )
        result = await self.db.execute(stmt)
        records = result.scalars().all()
        record_map = {r.snapshot_date: r.net_worth for r in records}

        # 為了保證即時圖表尾巴正確，今天若沒快照，自動補即時淨值
        if today not in record_map:
            try:
                summary = await self.get_summary(portfolio_id, force_refresh)
                record_map[today] = summary.net_worth
            except Exception:
                pass

        # 若快照涵蓋率達 80% 且至少有 2 天資料，則信任快照，使用簡單插值補齊缺漏
        # （新建的投資組合通常 records 是 0 或 1，將進入回溯模式）
        if len(records) > (days * 0.8) and len(records) > 1:
            history = []
            last_known_value = records[0].net_worth
            for i in range(days):
                current_date = start_date + timedelta(days=i)
                if current_date in record_map:
                    last_known_value = record_map[current_date]
                history.append(NetWorthHistoryItem(
                    date=f"{current_date.month}/{current_date.day}",
                    value=last_known_value
                ))
            return PortfolioHistoryResponse(portfolio_id=portfolio_id, history=history)

        # ====================
        # 啟動歷史淨值回溯引擎
        # ====================
        logger.info(f"啟動歷史淨值回溯引擎 (Portfolio: {portfolio_id}, Days: {days})")

        # A. 撈取所有該帳戶的交易紀錄 (由古至今)
        stmt_tx = (
            select(Transaction, AssetCategory.slug)
            .join(AssetCategory, Transaction.category_id == AssetCategory.id)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.asc())
        )
        tx_result = await self.db.execute(stmt_tx)
        tx_records = tx_result.all()

        if not tx_records:
            # 毫無交易紀錄，給條 0 的死心電圖
            history = []
            for i in range(days):
                d = start_date + timedelta(days=i)
                history.append(NetWorthHistoryItem(date=f"{d.month}/{d.day}", value=Decimal("0")))
            return PortfolioHistoryResponse(portfolio_id=portfolio_id, history=history)

        # B. 取出需要歷史報價的所有標的，並批次抓取
        symbols_to_fetch = set()
        for tx, slug in tx_records:
            if slug not in ("fiat", "liability"):
                symbols_to_fetch.add((tx.symbol, slug))

        timeframe = "1M"
        if days > 30: timeframe = "3M"
        if days > 90: timeframe = "1Y"
        if days > 365: timeframe = "5Y"

        import asyncio
        fetch_tasks = []
        for sym, slug in symbols_to_fetch:
            fetch_tasks.append(self.price_manager.get_historical_prices(sym, slug, timeframe))
        
        prices_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        history_prices = {}
        for (sym, _), p_result in zip(symbols_to_fetch, prices_results):
            if isinstance(p_result, Exception) or not p_result:
                history_prices[sym] = {}
                continue
            history_prices[sym] = {p.date.date(): p.close for p in p_result}

        # B-2. 由於歷史報價可能不含「今天即時正在跳動的價格」，也為它們補上 fallback
        current_prices = {}
        for sym, slug in symbols_to_fetch:
            try:
                cp = await self.price_manager.get_price(sym, slug)
                current_prices[sym] = cp.price
            except Exception:
                current_prices[sym] = Decimal("0")

        # 提供 TWD 匯率轉換
        usd_twd_rate = Decimal("32.0")
        try:
            rate_data = await self.price_manager.get_price("TWD=X", "us_stock")
            if rate_data.price > 0: usd_twd_rate = rate_data.price
        except Exception:
            pass

        def get_price_for_date(sym: str, target_date: date) -> Decimal:
            # 今天或未來 -> 即時報價
            if target_date >= today:
                return current_prices.get(sym, Decimal("0"))
            
            p_dict = history_prices.get(sym, {})
            if target_date in p_dict:
                return p_dict[target_date]
            
            # 若當天無報價（例如假日），往前找最多 7 天
            for j in range(1, 8):
                prev_date = target_date - timedelta(days=j)
                if prev_date in p_dict:
                    return p_dict[prev_date]
            
            # 真的找不到歷史（可能是 timeframe 沒抓夠長，或是下市），拿最新價暫代
            return current_prices.get(sym, Decimal("0"))

        # C. 逐日回溯推演 (Replay)
        holdings = {} # (symbol, slug) -> quantity
        tx_idx = 0
        total_txs = len(tx_records)
        history = []

        # 在這 N 天之前，先把以前的交易執行完，為庫存打底
        while tx_idx < total_txs and tx_records[tx_idx][0].executed_at.date() < start_date:
            tx, slug = tx_records[tx_idx]
            key = (tx.symbol, slug)
            qty = Decimal(str(tx.quantity))
            if tx.tx_type in ("buy", "deposit", "dividend"):
                holdings[key] = holdings.get(key, Decimal("0")) + qty
            elif tx.tx_type in ("sell", "withdraw"):
                holdings[key] = holdings.get(key, Decimal("0")) - qty
            tx_idx += 1

        # 開始印出視窗內的每一天
        for i in range(days):
            current_date = start_date + timedelta(days=i)

            # 把發生在今天的交易結算進來
            while tx_idx < total_txs and tx_records[tx_idx][0].executed_at.date() == current_date:
                tx, slug = tx_records[tx_idx]
                key = (tx.symbol, slug)
                qty = Decimal(str(tx.quantity))
                if tx.tx_type in ("buy", "deposit", "dividend"):
                    holdings[key] = holdings.get(key, Decimal("0")) + qty
                elif tx.tx_type in ("sell", "withdraw"):
                    holdings[key] = holdings.get(key, Decimal("0")) - qty
                tx_idx += 1

            # 根據今天的持倉總數，算出現值
            daily_net_worth = Decimal("0")
            for (sym, slug), qty in holdings.items():
                if qty == 0: continue
                
                if slug == "liability":
                    daily_net_worth -= qty
                elif slug == "fiat":
                    daily_net_worth += qty
                else:
                    price = get_price_for_date(sym, current_date)
                    mult = usd_twd_rate if slug in ("us_stock", "crypto") else Decimal("1")
                    daily_net_worth += (qty * price * mult)

            # 若今天有快照則無條件信任快照，否則用回推算出的值
            final_val = record_map.get(current_date, daily_net_worth)

            history.append(NetWorthHistoryItem(
                date=f"{current_date.month}/{current_date.day}",
                value=final_val
            ))

        return PortfolioHistoryResponse(
            portfolio_id=portfolio_id,
            history=history
        )
