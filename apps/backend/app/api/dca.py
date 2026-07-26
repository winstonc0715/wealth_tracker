"""
定期定額 API 路由

管理定期定額計畫與執行紀錄。
"""

import logging
from datetime import date, timedelta

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Response, UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.portfolio import Portfolio
from app.models.dca import ExecutionStatus
from app.api.auth import get_current_user
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.dca import (
    DCAScheduleCreate,
    DCAScheduleUpdate,
    DCAScheduleResponse,
    DCAExecutionResponse,
    DCAExecutionConfirm,
    DCAImportColumnInfo,
    DCAImportRecord,
    DCAImportResult,
)
from app.broker.dca_csv_parser import (
    DCACSVParser,
    build_template_csv,
    get_import_column_info,
)
from app.services.dca_service import DCAService

logger = logging.getLogger(__name__)

dca_router = APIRouter(prefix="/dca", tags=["定期定額"])


def _build_schedule_response(schedule) -> DCAScheduleResponse:
    """將 DCASchedule ORM 物件轉換為回應 Schema"""
    # 計算待確認筆數
    pending_count = sum(
        1 for e in (schedule.executions or [])
        if e.status == ExecutionStatus.PENDING
    )

    # 計算下次執行日期
    next_date = _calculate_next_execution_date(
        schedule.get_execution_days(),
        schedule.is_active,
    )

    return DCAScheduleResponse(
        id=schedule.id,
        user_id=schedule.user_id,
        portfolio_id=schedule.portfolio_id,
        symbol=schedule.symbol,
        asset_name=schedule.asset_name,
        category_id=schedule.category_id,
        broker=schedule.broker,
        investment_type=schedule.investment_type,
        target_amount=schedule.target_amount,
        target_shares=schedule.target_shares,
        execution_days=schedule.get_execution_days(),
        fee_discount=schedule.fee_discount,
        auto_confirm=schedule.auto_confirm,
        is_active=schedule.is_active,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        next_execution_date=next_date,
        pending_count=pending_count,
    )


def _calculate_next_execution_date(
    execution_days: list[int], is_active: bool,
) -> date | None:
    """計算下一個執行日期"""
    if not is_active or not execution_days:
        return None

    today = date.today()
    # 搜尋未來 62 天內最近的執行日（跨月考量）
    for delta in range(1, 63):
        candidate = today + timedelta(days=delta)
        if candidate.day in execution_days:
            # 排除週末
            if candidate.weekday() < 5:
                return candidate
    return None


def _build_execution_response(execution) -> DCAExecutionResponse:
    """將 DCAExecution ORM 物件轉換為回應 Schema"""
    schedule = execution.schedule
    return DCAExecutionResponse(
        id=execution.id,
        schedule_id=execution.schedule_id,
        execution_date=execution.execution_date,
        status=execution.status,
        estimated_price=execution.estimated_price,
        actual_price=execution.actual_price,
        quantity=execution.quantity,
        fee=execution.fee,
        total_cost=execution.total_cost,
        transaction_id=execution.transaction_id,
        note=execution.note,
        created_at=execution.created_at,
        confirmed_at=execution.confirmed_at,
        schedule_symbol=schedule.symbol if schedule else None,
        schedule_asset_name=schedule.asset_name if schedule else None,
    )


# ==================== 排程管理端點 ====================


@dca_router.post(
    "/schedules",
    response_model=ApiResponse[DCAScheduleResponse],
)
async def create_schedule(
    data: DCAScheduleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """建立定期定額計畫"""
    service = DCAService(db)
    try:
        schedule = await service.create_schedule(user.id, data)
        await db.commit()
        await db.refresh(schedule)
        return ApiResponse(
            data=_build_schedule_response(schedule),
            message="定期定額計畫已建立",
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@dca_router.get(
    "/schedules",
    response_model=ApiResponse[list[DCAScheduleResponse]],
)
async def get_schedules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得用戶所有定期定額計畫"""
    service = DCAService(db)
    schedules = await service.get_user_schedules(user.id)
    items = [_build_schedule_response(s) for s in schedules]
    return ApiResponse(data=items)


@dca_router.patch(
    "/schedules/{schedule_id}",
    response_model=ApiResponse[DCAScheduleResponse],
)
async def update_schedule(
    schedule_id: str,
    data: DCAScheduleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新定期定額計畫"""
    service = DCAService(db)
    try:
        schedule = await service.update_schedule(user.id, schedule_id, data)
        await db.commit()
        await db.refresh(schedule)
        return ApiResponse(
            data=_build_schedule_response(schedule),
            message="定期定額計畫已更新",
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@dca_router.delete(
    "/schedules/{schedule_id}",
    response_model=ApiResponse[bool],
)
async def delete_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """刪除定期定額計畫"""
    service = DCAService(db)
    try:
        await service.delete_schedule(user.id, schedule_id)
        await db.commit()
        return ApiResponse(data=True, message="定期定額計畫已刪除")
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@dca_router.post(
    "/schedules/{schedule_id}/toggle",
    response_model=ApiResponse[DCAScheduleResponse],
)
async def toggle_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切換定期定額計畫啟用/停用"""
    service = DCAService(db)
    try:
        schedule = await service.toggle_schedule(user.id, schedule_id)
        await db.commit()
        await db.refresh(schedule)
        status_text = "啟用" if schedule.is_active else "停用"
        return ApiResponse(
            data=_build_schedule_response(schedule),
            message=f"定期定額計畫已{status_text}",
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 執行紀錄端點 ====================


@dca_router.get(
    "/executions/pending",
    response_model=ApiResponse[list[DCAExecutionResponse]],
)
async def get_pending_executions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得所有待確認的定期定額執行紀錄"""
    service = DCAService(db)
    executions = await service.get_pending_executions(user.id)
    items = [_build_execution_response(e) for e in executions]
    return ApiResponse(data=items)


@dca_router.get(
    "/executions/history",
    response_model=ApiResponse[PaginatedResponse[DCAExecutionResponse]],
)
async def get_execution_history(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得定期定額執行歷史（分頁）"""
    service = DCAService(db)
    executions, total = await service.get_execution_history(
        user.id, page, page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    items = [_build_execution_response(e) for e in executions]
    return ApiResponse(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@dca_router.post(
    "/executions/{execution_id}/confirm",
    response_model=ApiResponse[DCAExecutionResponse],
)
async def confirm_execution(
    execution_id: str,
    data: DCAExecutionConfirm,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """確認定期定額執行並建立交易紀錄"""
    service = DCAService(db)
    try:
        execution = await service.confirm_execution(
            user.id, execution_id, data,
        )
        await db.commit()
        return ApiResponse(
            data=_build_execution_response(execution),
            message="執行已確認，交易紀錄已建立",
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@dca_router.post(
    "/executions/{execution_id}/skip",
    response_model=ApiResponse[DCAExecutionResponse],
)
async def skip_execution(
    execution_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """跳過定期定額執行"""
    service = DCAService(db)
    try:
        execution = await service.skip_execution(user.id, execution_id)
        await db.commit()
        return ApiResponse(
            data=_build_execution_response(execution),
            message="此次執行已跳過",
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 匯入端點 ====================


async def _load_dca_csv_records(
    file: UploadFile,
    broker_format: str,
    broker: str,
) -> tuple[list[DCAImportRecord], list[str]]:
    """讀取並解析上傳的 DCA CSV，回傳 (紀錄, 解析錯誤)。"""
    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail="CSV 必須使用 UTF-8 編碼") from e

    try:
        parser = DCACSVParser(broker_format=broker_format, broker=broker)
        return parser.parse(csv_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _merge_parse_errors(
    result: DCAImportResult, parse_errors: list[str],
) -> None:
    """把解析階段的錯誤併入匯入結果統計。"""
    if not parse_errors:
        return
    result.total_rows += len(parse_errors)
    result.skipped += len(parse_errors)
    result.errors = parse_errors + result.errors


@dca_router.get(
    "/import-template",
    response_class=Response,
)
async def download_import_template():
    """下載定期定額匯入 CSV 範本（標準格式，UTF-8 含 BOM）。"""
    csv_text = build_template_csv()
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="dca_import_template.csv"',
        },
    )


@dca_router.get(
    "/import-columns",
    response_model=ApiResponse[list[DCAImportColumnInfo]],
)
async def get_import_columns():
    """取得匯入 CSV 支援的欄位、必填狀態與欄位名稱別名對照。"""
    return ApiResponse(data=get_import_column_info())


@dca_router.post(
    "/import-csv/preview",
    response_model=ApiResponse[DCAImportResult],
)
async def preview_dca_csv(
    portfolio_id: str = Form(...),
    category_id: int = Form(1),
    broker_format: str = Form("standard"),
    broker: str = Form("sinopac"),
    auto_confirm: bool = Form(False),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    匯入預覽（dry-run）。

    以與正式匯入完全相同的邏輯試算，回傳逐列明細與統計後
    rollback，不會寫入任何資料。
    """
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    records, parse_errors = await _load_dca_csv_records(
        file, broker_format, broker,
    )

    service = DCAService(db)
    try:
        result = await service.import_records(
            user_id=user.id,
            portfolio_id=portfolio_id,
            category_id=category_id,
            records=records,
            default_broker=broker,
            auto_confirm=auto_confirm,
            collect_details=True,
        )
    except Exception as e:
        await db.rollback()
        logger.exception("定期定額匯入預覽失敗")
        raise HTTPException(status_code=500, detail=f"預覽失敗: {str(e)}")

    # dry-run：無論結果如何都不落地
    await db.rollback()

    result.dry_run = True
    _merge_parse_errors(result, parse_errors)
    return ApiResponse(
        data=result,
        message=(
            f"預覽完成（未寫入資料）：{result.imported} 筆可匯入，"
            f"{result.skipped} 筆有問題"
        ),
    )


@dca_router.post(
    "/import-csv",
    response_model=ApiResponse[DCAImportResult],
)
async def import_dca_csv(
    portfolio_id: str = Form(...),
    category_id: int = Form(1),
    broker_format: str = Form("standard"),
    broker: str = Form("sinopac"),
    auto_confirm: bool = Form(False),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    匯入定期定額扣款資料。

    重複匯入同一標的與同一扣款日會更新既有執行紀錄；若已入帳，
    會同步更新原交易，避免重複建立交易。
    """
    portfolio = await db.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="投資組合不存在")

    records, parse_errors = await _load_dca_csv_records(
        file, broker_format, broker,
    )

    service = DCAService(db)
    try:
        result = await service.import_records(
            user_id=user.id,
            portfolio_id=portfolio_id,
            category_id=category_id,
            records=records,
            default_broker=broker,
            auto_confirm=auto_confirm,
        )
        _merge_parse_errors(result, parse_errors)
        await db.commit()
        return ApiResponse(
            data=result,
            message=(
                f"定期定額匯入完成：{result.imported} 筆成功，"
                f"{result.skipped} 筆略過"
            ),
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.exception("定期定額匯入失敗")
        raise HTTPException(status_code=500, detail=f"匯入失敗: {str(e)}")


@dca_router.post(
    "/execute-now",
    response_model=ApiResponse[dict],
)
async def execute_now(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手動觸發今日定期定額排程（除錯用）"""
    service = DCAService(db)
    try:
        result = await service.execute_pending_schedules()
        await db.commit()
        return ApiResponse(
            data=result,
            message="定期定額排程已手動執行",
        )
    except Exception as e:
        await db.rollback()
        logger.exception("手動執行定期定額排程失敗")
        raise HTTPException(
            status_code=500,
            detail=f"執行失敗: {str(e)}",
        )
