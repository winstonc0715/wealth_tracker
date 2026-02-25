"""
WealthTracker 後端設定模組

使用 Pydantic Settings 管理環境變數，自動驗證型別與預設值。
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """應用程式設定，透過環境變數或 .env 載入"""

    # === 應用程式 ===
    app_env: Literal["development", "production", "testing"] = "development"
    app_name: str = "WealthTracker API"
    app_version: str = "0.1.0"
    debug: bool = True

    # === 安全性 ===
    secret_key: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 天 (30 * 24 * 60)
    admin_emails: str = "demo@wealth.com"  # 逗號分隔的管理員 Email 清單
    google_client_id: str = ""  # Google OAuth Client ID

    # === 資料庫 ===
    # 預設使用 SQLite（開發模式），生產環境切換為 PostgreSQL
    database_url: str = "sqlite+aiosqlite:///./wealth_tracker.db"

    # === Redis ===
    redis_url: str | None = None  # None 時自動使用記憶體快取

    # === 報價 API ===
    coingecko_api_key: str = ""
    finnhub_api_key: str = ""
    fugle_api_key: str = ""
    price_cache_ttl: int = 300  # 5 分鐘

    # === CORS ===
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8081",
        "https://wealth-tracker-web-brown.vercel.app",
        "https://wealthtracker-web.vercel.app",
    ]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def admin_email_list(self) -> list[str]:
        """回傳管理員 Email 清單"""
        if not self.admin_emails:
            return []
        return [e.strip() for e in self.admin_emails.split(",")]

    @property
    def use_sqlite(self) -> bool:
        """判斷是否使用 SQLite（開發模式）"""
        return "sqlite" in self.database_url


@lru_cache
def get_settings() -> Settings:
    """取得快取的設定實例"""
    return Settings()
