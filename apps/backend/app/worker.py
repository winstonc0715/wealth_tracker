"""
背景報價同步器 (Background Price Worker)

使用 APScheduler 定期從資料庫撈取所有使用者持有的不重複標的，
並批次向外部 API (Tw_stock, CoinGecko, Yahoo) 要求最新報價並寫入 Redis 快取。
此機制可防範高併發快取擊穿與超過 Rate Limit 限制。
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, distinct

from app.database import async_session
from app.models.position import CurrentPosition
from app.models.asset_category import AssetCategory
from app.models.portfolio import Portfolio
from app.price.manager import PriceManager
from app.services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)

# 使用 AsyncIOScheduler
scheduler = AsyncIOScheduler()


async def sync_all_prices():
    """
    背景排程任務：取得全站所有用戶持有的標的，呼叫 PriceManager 進行批次更新快取
    """
    logger.info("開始背景同步全站報價...")
    
    try:
        async with async_session() as session:
            # 取得所有不重複的 (symbol, category_id) 以及對應的 category_slug
            stmt = select(
                distinct(CurrentPosition.symbol),
                AssetCategory.slug
            ).join(
                AssetCategory, CurrentPosition.category_id == AssetCategory.id
            )
            result = await session.execute(stmt)
            rows = result.all()
            
            if not rows:
                logger.info("目前沒有任何持倉標的需要同步。")
                return
            
            # 準備查詢清單 [(symbol, category_slug), ...]
            items = [(row[0], row[1]) for row in rows]
            
            # 使用 PriceManager 批次取得報價，強制穿透快取 (force_refresh=True)
            manager = PriceManager()
            # 這裡的 get_prices_batch 內部會將結果寫入快取
            await manager.get_prices_batch(items, force_refresh=True)
            await manager.close()
            
            logger.info("背景同步全站報價完成 (共 %d 筆不重複標的)", len(items))
            
    except Exception as e:
        logger.error("背景同步全站報價失敗: %s", e)


async def record_all_portfolios_snapshot():
    """
    背景排程任務：遍歷全站所有投資組合，儲存當前淨值快照
    """
    logger.info("開始記錄全站投資組合淨值快照...")
    
    try:
        async with async_session() as session:
            # 取得所有投資組合
            stmt = select(Portfolio)
            result = await session.execute(stmt)
            portfolios = result.scalars().all()
            
            if not portfolios:
                logger.info("沒有任何投資組合需要記錄。")
                return
            
            # 使用 PortfolioService 進行儲存
            service = PortfolioService(session)
            for pf in portfolios:
                try:
                    await service.save_net_worth_snapshot(pf.id)
                except Exception as ex:
                    logger.error("記錄投資組合 %s 淨值失敗: %s", pf.id, ex)
            
            await session.commit()
            logger.info("背景記錄全站淨值快照完成 (共 %d 個投資組合)", len(portfolios))
            
    except Exception as e:
        logger.error("背景記錄全站淨值快照失敗: %s", e)


def setup_worker():
    """設定並啟動排程器"""
    # 設定每 1 分鐘執行一次
    scheduler.add_job(
        sync_all_prices, 
        'interval', 
        minutes=1, 
        id='sync_all_prices_job',
        replace_existing=True
    )
    # 設定每 1 小時記錄一次淨值 (save_net_worth_snapshot 會自動處理當日更新)
    scheduler.add_job(
        record_all_portfolios_snapshot,
        'interval',
        hours=1,
        id='record_all_portfolios_snapshot_job',
        replace_existing=True
    )
    scheduler.start()
    logger.info("✅ 背景報價同步器 (Background Worker) 已啟動")


def stop_worker():
    """停止排程器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("背景報價同步器已關閉")
