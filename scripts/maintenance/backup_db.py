"""
WealthTracker 本地排程備份腳本
讀取遠端資料庫並匯出所有的資料至 JSON 檔案中，保留最近的 7 份備份。
"""

import json
import asyncio
from datetime import datetime, date
import os
import sys

# 將 apps/backend 加入 sys.path (因為腳本是從 scripts/maintenance 這裡執行)
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../apps/backend'))
sys.path.insert(0, backend_dir)

from sqlalchemy.future import select
from app.database import async_session
from app.models import User, AssetCategory, Portfolio, Transaction, CurrentPosition, HistoricalNetWorth

def default_serializer(obj):
    """處理 datetime 等物件的 JSON 序列化"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

async def dump_table(session, model):
    """將 SQLAlchemy Model 所有資料轉為字典的串列"""
    result = await session.execute(select(model))
    rows = result.scalars().all()
    return [
        {col.name: getattr(row, col.name) for col in row.__table__.columns}
        for row in rows
    ]

async def backup_database():
    print("啟動 WealthTracker 備份程序...")
    backup_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backups'))
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(backup_dir, f"wealth_tracker_backup_{timestamp}.json")
    
    data = {}
    try:
        async with async_session() as session:
            data['users'] = await dump_table(session, User)
            data['asset_categories'] = await dump_table(session, AssetCategory)
            data['portfolios'] = await dump_table(session, Portfolio)
            data['transactions'] = await dump_table(session, Transaction)
            data['current_positions'] = await dump_table(session, CurrentPosition)
            data['historical_net_worth'] = await dump_table(session, HistoricalNetWorth)
    except Exception as e:
        print(f"❌ 備份失敗，無法連上資料庫: {e}")
        sys.exit(1)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, default=default_serializer, indent=2, ensure_ascii=False)
        
    print(f"✅ 備份成功: {filepath}")
    
    # 清理舊備份 (保留最近 7 份)
    backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('wealth_tracker_backup_')])
    if len(backups) > 7:
        for old_file in backups[:-7]:
            old_path = os.path.join(backup_dir, old_file)
            if os.path.isfile(old_path):
                os.remove(old_path)
                print(f"🗑️ 刪除舊備份 (超過 7 份限制): {old_file}")

if __name__ == "__main__":
    asyncio.run(backup_database())
