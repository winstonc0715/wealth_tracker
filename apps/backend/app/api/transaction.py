"""
交易與券商 API 路由

新增交易、交易紀錄查詢、CSV 匯入、部位比對。
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.portfolio import Portfolio
from app.broker.csv_parser import CSVParser
from app.broker.reconciliation import ReconciliationService
from app.services.transaction_service import TransactionService
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.transaction import (
    TransactionCreate, TransactionResponse,
    CSVImportResult, ReconciliationResult,
)
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["交易"])
broker_router = APIRouter(prefix="/broker", tags=["券商同步"])


@router.post("/", response_model=ApiResponse[TransactionResponse])
async def create_transaction(
    data: TransactionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    新增交易紀錄

    自動觸發更新 current_positions（持倉部位）。
    """
    # 驗證投資組合歸屬
    portfolio = await db.get(Portfolio, data.portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    service = TransactionService(db)
    tx = await service.create_transaction(data)
    await db.refresh(tx)

    return ApiResponse(
        data=TransactionResponse(
            id=tx.id,
            portfolio_id=tx.portfolio_id,
            category_id=tx.category_id,
            category_name=tx.category.name if tx.category else None,
            symbol=tx.symbol,
            asset_name=tx.asset_name,
            tx_type=tx.tx_type,
            quantity=tx.quantity,
            unit_price=tx.unit_price,
            fee=tx.fee,
            currency=tx.currency,
            executed_at=tx.executed_at,
            note=tx.note,
            realized_pnl=tx.realized_pnl,
            created_at=tx.created_at,
        ),
        message="交易已新增",
    )


@router.get(
    "/{portfolio_id}",
    response_model=ApiResponse[PaginatedResponse[TransactionResponse]],
)
async def get_transactions(
    portfolio_id: str,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得投資組合交易紀錄（分頁）"""
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    service = TransactionService(db)
    transactions, total = await service.get_transactions(
        portfolio_id, page, page_size
    )

    total_pages = (total + page_size - 1) // page_size
    items = [
        TransactionResponse(
            id=tx.id,
            portfolio_id=tx.portfolio_id,
            category_id=tx.category_id,
            category_name=tx.category.name if tx.category else None,
            symbol=tx.symbol,
            asset_name=tx.asset_name,
            tx_type=tx.tx_type,
            quantity=tx.quantity,
            unit_price=tx.unit_price,
            fee=tx.fee,
            currency=tx.currency,
            executed_at=tx.executed_at,
            note=tx.note,
            realized_pnl=tx.realized_pnl,
            created_at=tx.created_at,
        )
        for tx in transactions
    ]

    return ApiResponse(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.patch("/{tx_id}", response_model=ApiResponse[TransactionResponse])
async def update_transaction(
    tx_id: str,
    data: "TransactionUpdate",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新交易紀錄並自動重算部位與損益"""
    tx = await db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="交易紀錄不存在")
    
    # 驗證投資組合歸屬
    portfolio = await db.get(Portfolio, tx.portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=403, detail="無權限修改此交易")

    service = TransactionService(db)
    try:
        updated_tx = await service.update_transaction(tx_id, data)
        await db.refresh(updated_tx)
        return ApiResponse(
            data=TransactionResponse.model_validate(updated_tx),
            message="交易已更新，損益已重新計算"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recalculate/all", tags=["維護"])
async def recalculate_all_pnl(
    db: AsyncSession = Depends(get_db), # Changed from get_async_session to get_db
    current_user: User = Depends(get_current_user),
):
    """手動觸發全系統實現損益重算 (管理員功能)"""
    # Moved imports to top for consistency, but keeping them here as per user's snippet structure
    from app.config import get_settings
    
    settings = get_settings()
    if current_user.email not in settings.admin_email_list:
        raise HTTPException(status_code=403, detail="僅限管理員執行")
    
    service = TransactionService(db)
    result = await service.recalculate_all_portfolios()
    await db.commit()
    
    return {"message": "全系統損益重算完成", "detail": result}


@router.delete("/{tx_id}", response_model=ApiResponse[bool])
async def delete_transaction(
    tx_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """刪除交易紀錄並自動重算部位與損益"""
    tx = await db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="交易紀錄不存在")
    
    # 驗證投資組合歸屬
    portfolio = await db.get(Portfolio, tx.portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=403, detail="無權限刪除此交易")

    service = TransactionService(db)
    try:
        await service.delete_transaction(tx_id)
        return ApiResponse(data=True, message="交易已刪除，損益已重新計算")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# === 券商同步路由 ===


@broker_router.post("/import-csv", response_model=ApiResponse[CSVImportResult])
async def import_csv(
    portfolio_id: str = Form(...),
    category_id: int = Form(1),
    broker_format: str = Form("standard"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CSV 匯入交易紀錄

    支援格式：standard（標準）、sinopac（永豐）、fubon（富邦）、cathay（國泰）
    """
    # 驗證投資組合歸屬
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    # 讀取 CSV 內容
    content = await file.read()
    csv_text = content.decode("utf-8-sig")  # 支援 BOM

    # 解析 CSV
    try:
        parser = CSVParser(broker_format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    transactions, errors = parser.parse(csv_text, portfolio_id, category_id)

    # 批次寫入交易
    service = TransactionService(db)
    imported = 0
    for tx_data in transactions:
        try:
            await service.create_transaction(tx_data)
            imported += 1
        except Exception as e:
            errors.append(f"寫入失敗 ({tx_data.symbol}): {e}")

    return ApiResponse(
        data=CSVImportResult(
            total_rows=len(transactions) + len(errors),
            imported=imported,
            skipped=len(errors),
            errors=errors[:20],  # 最多顯示 20 個錯誤
        ),
        message=f"匯入完成：{imported} 筆成功",
    )


@broker_router.post(
    "/reconcile/{portfolio_id}",
    response_model=ApiResponse[ReconciliationResult],
)
async def reconcile_positions(
    portfolio_id: str,
    external_positions: dict[str, float],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    部位比對

    將外部持倉資料與系統內的 current_positions 進行比對。
    """
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    # 轉換為 Decimal
    ext_positions = {
        symbol: Decimal(str(qty))
        for symbol, qty in external_positions.items()
    }

    service = ReconciliationService(db)
    result = await service.reconcile(portfolio_id, ext_positions)

    return ApiResponse(data=result)
