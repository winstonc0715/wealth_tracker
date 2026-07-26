"""
負債管理 API 路由
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.portfolio import Portfolio
from app.api.auth import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.liability import (
    LiabilityCreate, LiabilityUpdate, PaymentCreate,
    LiabilityResponse, PaymentResponse, BackfillPreview,
)
from app.services.liability_service import LiabilityService

logger = logging.getLogger(__name__)

liability_router = APIRouter(prefix="/liabilities", tags=["負債管理"])


async def _check_portfolio(
    db: AsyncSession, portfolio_id: str, user: User
) -> None:
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")


@liability_router.get(
    "/{portfolio_id}", response_model=ApiResponse[list[LiabilityResponse]]
)
async def list_liabilities(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得投資組合的所有負債（含進度統計）"""
    await _check_portfolio(db, portfolio_id, user)
    service = LiabilityService(db)
    return ApiResponse(data=await service.list_liabilities(user.id, portfolio_id))


@liability_router.post("/", response_model=ApiResponse[LiabilityResponse])
async def create_liability(
    data: LiabilityCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """建立負債（未綁定既有持倉時自動建立負債持倉）"""
    await _check_portfolio(db, data.portfolio_id, user)
    service = LiabilityService(db)
    try:
        liability = await service.create_liability(user.id, data)
        return ApiResponse(
            data=await service.get_liability(user.id, liability.id),
            message="負債已建立",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@liability_router.patch(
    "/{liability_id}", response_model=ApiResponse[LiabilityResponse]
)
async def update_liability(
    liability_id: str,
    data: LiabilityUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新負債設定"""
    service = LiabilityService(db)
    try:
        await service.update_liability(user.id, liability_id, data)
        return ApiResponse(
            data=await service.get_liability(user.id, liability_id),
            message="負債已更新",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@liability_router.delete("/{liability_id}")
async def delete_liability(
    liability_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """刪除負債主檔（保留交易紀錄與持倉）"""
    service = LiabilityService(db)
    try:
        await service.delete_liability(user.id, liability_id)
        return ApiResponse(message="負債已刪除")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@liability_router.post(
    "/{liability_id}/payments", response_model=ApiResponse[PaymentResponse]
)
async def record_payment(
    liability_id: str,
    data: PaymentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """記錄一筆還款（自動沖減負債餘額）"""
    service = LiabilityService(db)
    try:
        payment = await service.record_payment(user.id, liability_id, data)
        return ApiResponse(
            data=PaymentResponse.model_validate(payment),
            message="還款已記錄",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@liability_router.get(
    "/{liability_id}/backfill", response_model=ApiResponse[BackfillPreview]
)
async def preview_backfill(
    liability_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """預覽依日期推算的待補登期數與金額（不寫入）"""
    service = LiabilityService(db)
    try:
        return ApiResponse(
            data=await service.preview_backfill(user.id, liability_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@liability_router.post(
    "/{liability_id}/backfill", response_model=ApiResponse[LiabilityResponse]
)
async def backfill_payments(
    liability_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """依日期推算自動補登過往還款（餘額同步沖減、歸零自動結清）"""
    service = LiabilityService(db)
    try:
        count = await service.backfill_payments(user.id, liability_id)
        return ApiResponse(
            data=await service.get_liability(user.id, liability_id),
            message=f"已補登 {count} 期還款",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@liability_router.delete("/{liability_id}/payments/{payment_id}")
async def delete_payment(
    liability_id: str,
    payment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """刪除還款紀錄（連同沖減交易，餘額自動回補）"""
    service = LiabilityService(db)
    try:
        await service.delete_payment(user.id, liability_id, payment_id)
        return ApiResponse(message="還款紀錄已刪除")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
