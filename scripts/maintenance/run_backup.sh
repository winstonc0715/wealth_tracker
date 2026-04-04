#!/bin/bash
# 確保腳本在發生錯誤時停止
set -e

# 定義絕對路徑
PROJECT_ROOT="/Users/zhanghansheng/Downloads/project/wealth_tracker"
BACKEND_DIR="${PROJECT_ROOT}/apps/backend"
MAINTENANCE_DIR="${PROJECT_ROOT}/scripts/maintenance"
LOG_FILE="${PROJECT_ROOT}/logs/backup.log"

echo "======================================" >> "${LOG_FILE}"
echo "開始備份執行: $(date)" >> "${LOG_FILE}"

# 進入到 backend 確保 pydantic 能讀取正確的 .env 設定
cd "${BACKEND_DIR}"

# 執行 python 腳本
if "${BACKEND_DIR}/.venv/bin/python" "${MAINTENANCE_DIR}/backup_db.py" >> "${LOG_FILE}" 2>&1; then
    echo "備份完成: $(date)" >> "${LOG_FILE}"
else
    echo "⚠️ 備份發生錯誤: $(date)" >> "${LOG_FILE}"
    exit 1
fi
