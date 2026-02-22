#!/bin/bash
set -e

# 等待資料庫就緒（使用 TCP socket 檢查，不依賴 psycopg2）
python << END
import sys
import os
import time
import socket
import re

db_url = os.getenv("DATABASE_URL")
if not db_url or "sqlite" in db_url:
    print("Using SQLite or no DB URL provided. Skipping wait.")
    sys.exit(0)

# 從 URL 中提取主機與端口
match = re.search(r"@([^:/]+):(\d+)", db_url)
if not match:
    print("Could not parse DATABASE_URL. Skipping wait.")
    sys.exit(0)

host, port = match.group(1), int(match.group(2))
print(f"Waiting for database at {host}:{port}...")

for i in range(15):
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        print("Database is ready!")
        sys.exit(0)
    except (socket.error, OSError) as e:
        print(f"Database not ready yet... {e}")
        time.sleep(2)

print("Could not connect to database. Moving on anyway...")
END


# Run migrations if migrations directory exists
if [ -d "alembic" ]; then
    echo "Running alembic migrations..."
    alembic upgrade head
else
    echo "Alembic migrations directory not found. Skipping migrations."
fi

# Start application
echo "Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
