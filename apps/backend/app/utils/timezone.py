"""
時區工具

伺服器（Render）以 UTC 執行，但用戶在台灣：所有「今天是幾號」的
日曆判斷（快照日期、還款日、DCA 執行日）都必須以台北時間為準，
否則台北 00:00–08:00 之間會落在前一天。
時間戳記（created_at 等）仍以 UTC 儲存，不受影響。
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def taipei_now() -> datetime:
    """目前的台北時間（aware datetime）"""
    return datetime.now(TAIPEI_TZ)


def taipei_today() -> date:
    """台北時區的今天日期"""
    return taipei_now().date()
