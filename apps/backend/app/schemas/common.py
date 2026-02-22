"""
共用 Schema 定義

包含分頁、API 回應包裝等通用結構。
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """統一 API 回應格式"""
    success: bool = True
    data: T | None = None
    message: str = "OK"


class ErrorResponse(BaseModel):
    """錯誤回應格式"""
    success: bool = False
    error: str
    detail: str | None = None


class PaginationParams(BaseModel):
    """分頁參數"""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """分頁回應"""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class TimestampMixin(BaseModel):
    """時間戳 Mixin"""
    created_at: datetime | None = None
    updated_at: datetime | None = None
