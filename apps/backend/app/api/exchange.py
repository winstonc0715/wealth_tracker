"""
匯率 API 路由
"""

import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.price.manager import PriceManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio/exchange-rates", tags=["匯率"])


@router.get("", response_model=ApiResponse[dict[str, float]])
async def get_exchange_rates(
    user: User = Depends(get_current_user),
):
    """
    取得目前匯率 (基準為 TWD)
    
    回傳形式:
    {
        "USD": 32.15,  # 1 USD = 32.15 TWD
        "TWD": 1.0     # 基準幣別
    }
    """
    try:
        manager = PriceManager()
        # 從 Yahoo Finance 抓取 USD/TWD 匯率 (代碼 TWD=X)
        # 由於 yfinance 的 TWD=X 報價代表 1 USD 換多少 TWD
        price_data = await manager.get_price("TWD=X", "us_stock")
        
        rate = float(price_data.price)
        if rate <= 0:
            rate = 32.0 # Fallback 預設值
            
        return ApiResponse(data={
            "USD": rate,
            "TWD": 1.0
        })
    except Exception as e:
        logger.error("取得匯率失敗: %s", e)
        # 若發生錯誤，回傳一個合理預設值讓前端不崩潰
        return ApiResponse(data={
            "USD": 32.0,
            "TWD": 1.0
        })
