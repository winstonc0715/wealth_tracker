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
from app.price.manager import PriceManager

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
    scheduler.start()
    logger.info("✅ 背景報價同步器 (Background Worker) 已啟動")


def stop_worker():
    """停止排程器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("背景報價同步器已關閉")
