"""
認證 API 路由

用戶註冊、登入、JWT Token 生成。
"""

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user import UserRegister, UserLogin, GoogleLogin, UserResponse, TokenResponse

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["認證"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def _create_token(user_id: str) -> str:
    """產生 JWT Token"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _verify_token(token: str) -> str | None:
    """驗證 JWT Token，回傳 user_id"""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """用戶註冊"""
    # 檢查 email 是否已存在
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="此 Email 已被註冊",
        )

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=pwd_context.hash(data.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return ApiResponse(data=UserResponse.model_validate(user))


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用戶登入"""
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email 或密碼錯誤",
        )

    # 如果用戶是透過 Google 註冊且未設定密碼
    if user.google_id and not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="此帳號已綁定 Google 登入，請使用 Google 登入或設定密碼後再試",
        )

    if not pwd_context.verify(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email 或密碼錯誤",
        )

    token = _create_token(user.id)
    return ApiResponse(
        data=TokenResponse(
            access_token=token,
            expires_in=settings.jwt_expire_minutes * 60,
        )
    )


@router.post("/google", response_model=ApiResponse[TokenResponse])
async def google_login(data: GoogleLogin, db: AsyncSession = Depends(get_db)):
    """Google OAuth 登入"""
    try:
        # 驗證 Google ID Token
        # 注意：在生產環境中需正確設定 CLIENT_ID，目前先不強制檢查以利開發調試
        # 若有設定 GOOGLE_CLIENT_ID 環境變數則會進行驗證
        idinfo = id_token.verify_oauth2_token(
            data.id_token, google_requests.Request(), settings.google_client_id
        )

        google_id = idinfo["sub"]
        email = idinfo["email"]
        name = idinfo.get("name", email.split("@")[0])

        # 1. 嘗試透過 google_id 查找
        stmt = select(User).where(User.google_id == google_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # 2. 嘗試透過 email 查找（處理先前已註冊但未綁定 Google 的用戶）
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                # 綁定 Google ID
                user.google_id = google_id
            else:
                # 3. 建立新用戶
                user = User(
                    email=email,
                    username=name,
                    google_id=google_id,
                    hashed_password=None, # 第三方登入暫不設密碼
                )
                db.add(user)

            await db.flush()
            await db.refresh(user)

        token = _create_token(user.id)
        return ApiResponse(
            data=TokenResponse(
                access_token=token,
                expires_in=settings.jwt_expire_minutes * 60,
            )
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google Token 驗證失敗",
        )
    except Exception as e:
        logger.error(f"Google 登入失敗: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系統處理 Google 登入時出錯",
        )


# === 依賴注入：取得當前用戶 ===

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """取得當前已認證的用戶"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供認證 Token",
        )

    user_id = _verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 無效或已過期",
        )

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶不存在或已停用",
        )

    return user
