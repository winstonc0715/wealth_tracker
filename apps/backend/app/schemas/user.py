"""
用戶相關 Schema

定義註冊、登入、用戶資料的請求與回應模型。
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """用戶註冊請求"""
    email: EmailStr
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    """用戶登入請求"""
    email: EmailStr
    password: str


class GoogleLogin(BaseModel):
    """Google OAuth 登入請求"""
    id_token: str


class UserResponse(BaseModel):
    """用戶資料回應"""
    id: str
    email: str
    username: str
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT Token 回應"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
