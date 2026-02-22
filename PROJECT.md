# WealthTracker - 跨平台資產管理系統

## 專案說明
跨平台資產管理系統，支援台股、美股、加密貨幣、法幣與負債追蹤。

## 技術棧
- **Monorepo**: Turborepo
- **後端**: FastAPI + SQLAlchemy + Alembic
- **資料庫**: PostgreSQL (生產) / SQLite (開發)
- **快取**: Redis (生產) / 記憶體快取 (開發)
- **Web 前端**: Next.js + Tailwind CSS + Recharts
- **行動端**: React Native Expo

## 專案結構
```
wealth_tracker/
├── apps/
│   ├── backend/       # FastAPI 後端
│   ├── web/           # Next.js Web 端
│   └── mobile/        # React Native Expo
└── packages/
    └── shared/        # 共用型別與 API Client
```

## 開發指令
```bash
# 安裝所有依賴
npm install

# 啟動所有服務
npm run dev

# 僅啟動後端
cd apps/backend && uvicorn app.main:app --reload

# 僅啟動 Web
cd apps/web && npm run dev
```
