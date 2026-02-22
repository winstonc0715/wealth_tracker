"""
投資組合 API 路由

投資組合 CRUD、淨值摘要、資產配置。
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.portfolio import Portfolio
from app.price.manager import PriceManager
from app.services.portfolio_service import PortfolioService
from app.schemas.common import ApiResponse
from app.schemas.portfolio import (
    PortfolioCreate, PortfolioUpdate, PortfolioResponse,
    PortfolioSummary, AllocationResponse, PortfolioHistoryResponse,
)
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["投資組合"])
settings = get_settings()


def _get_portfolio_service(db: AsyncSession) -> PortfolioService:
    """建立 PortfolioService 實例"""
    return PortfolioService(db, PriceManager())


@router.get("/", response_model=ApiResponse[list[PortfolioResponse]])
async def list_portfolios(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得用戶所有投資組合"""
    stmt = select(Portfolio).where(Portfolio.user_id == user.id)
    result = await db.execute(stmt)
    portfolios = result.scalars().all()
    return ApiResponse(
        data=[PortfolioResponse.model_validate(p) for p in portfolios]
    )


@router.post("/", response_model=ApiResponse[PortfolioResponse])
async def create_portfolio(
    data: PortfolioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """建立投資組合"""
    portfolio = Portfolio(
        user_id=user.id,
        name=data.name,
        description=data.description,
        base_currency=data.base_currency,
    )
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return ApiResponse(data=PortfolioResponse.model_validate(portfolio))


@router.get("/search", response_model=ApiResponse[list[dict]])
async def search_symbols(
    query: str,
    category_slug: str = "all",
    user: User = Depends(get_current_user),
):
    """
    即時搜尋標的代碼與名稱
    
    支援依據資產類別 (us_stock, tw_stock, crypto 等) 進行即時模糊搜尋。若傳入 'all' 則會並行查詢所有支援的類別。
    """
    manager = PriceManager()
    try:
        results = await manager.search_symbol(query=query, category_slug=category_slug)
        # 將 dataclass 轉為 dict 回傳
        return ApiResponse(data=[
            {
                "symbol": r.symbol,
                "name": r.name,
                "type_box": r.type_box,
                "exchange": r.exchange,
                "currency": r.currency,
                "category_slug": getattr(r, 'category_slug', category_slug)
            } for r in results
        ])
    except Exception as e:
        logger.error(f"搜尋標的失敗: {e}")
        return ApiResponse(data=[])
    finally:
        await manager.close()


@router.get("/{portfolio_id}", response_model=ApiResponse[PortfolioResponse])
async def get_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得單一投資組合"""
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")
    return ApiResponse(data=PortfolioResponse.model_validate(portfolio))


@router.put("/{portfolio_id}", response_model=ApiResponse[PortfolioResponse])
async def update_portfolio(
    portfolio_id: str,
    data: PortfolioUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新投資組合"""
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    if data.name is not None:
        portfolio.name = data.name
    if data.description is not None:
        portfolio.description = data.description

    await db.flush()
    return ApiResponse(data=PortfolioResponse.model_validate(portfolio))


@router.delete("/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """刪除投資組合"""
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    await db.delete(portfolio)
    return ApiResponse(message="投資組合已刪除")


@router.get("/{portfolio_id}/summary", response_model=ApiResponse[PortfolioSummary])
async def get_portfolio_summary(
    portfolio_id: str,
    force_refresh: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    計算投資組合淨值摘要

    即時讀取持倉部位，呼叫報價引擎取得最新價格，
    回傳總資產、總負債、淨值與未實現損益。
    """
    # 驗證權限
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    if force_refresh and user.email not in settings.admin_email_list:
        raise HTTPException(status_code=403, detail="無強制更新權限")

    service = _get_portfolio_service(db)
    try:
        summary = await service.get_summary(portfolio_id, force_refresh)
        return ApiResponse(data=summary)
    except Exception as e:
        logger.error("計算淨值失敗: %s", e)
        raise HTTPException(status_code=500, detail=f"計算淨值失敗: {e}")


@router.get(
    "/{portfolio_id}/allocations",
    response_model=ApiResponse[AllocationResponse],
)
async def get_allocations(
    portfolio_id: str,
    force_refresh: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    取得資產配置比例（圓餅圖用）

    依照資產類別分組，計算各類別佔總資產的百分比。
    """
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    if force_refresh and user.email not in settings.admin_email_list:
        raise HTTPException(status_code=403, detail="無強制更新權限")

    service = _get_portfolio_service(db)
    try:
        allocations = await service.get_allocations(portfolio_id, force_refresh)
        return ApiResponse(data=allocations)
    except Exception as e:
        logger.error("計算配置失敗: %s", e)
        raise HTTPException(status_code=500, detail=f"計算配置失敗: {e}")


@router.get(
    "/{portfolio_id}/history",
    response_model=ApiResponse[PortfolioHistoryResponse],
)
async def get_portfolio_history(
    portfolio_id: str,
    days: int = 30,
    force_refresh: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    取得投資組合歷史淨值走勢
    
    預設取得近 30 天資料，無資料的天數將自動以前一日淨值補齊。
    """
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    if force_refresh and user.email not in settings.admin_email_list:
        raise HTTPException(status_code=403, detail="無強制更新權限")

    service = _get_portfolio_service(db)
    try:
        history = await service.get_history(portfolio_id, days, force_refresh)
        return ApiResponse(data=history)
    except Exception as e:
        logger.error("取得歷史淨值失敗: %s", e)
        raise HTTPException(status_code=500, detail=f"取得歷史淨值失敗: {e}")
