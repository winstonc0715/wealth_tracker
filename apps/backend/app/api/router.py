"""
API 路由集中註冊
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.portfolio import router as portfolio_router
from app.api.transaction import router as transaction_router
from app.api.transaction import broker_router
from app.api.exchange import router as exchange_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(exchange_router) # 必須放在 portfolio 之前，避免被 /{id} 攔截
api_router.include_router(portfolio_router)
api_router.include_router(transaction_router)
api_router.include_router(broker_router)
