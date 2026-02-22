#!/bin/bash
set -e

# Wait for database if needed (optional for Railway, but good practice)
# We use Python here for a quick check if DATABASE_URL is reachable
python << END
import sys
import os
import time
from sqlalchemy import create_engine

db_url = os.getenv("DATABASE_URL")
if not db_url or "sqlite" in db_url:
    print("Using SQLite or no DB URL provided. Skipping wait.")
    sys.exit(0)

print(f"Waiting for database at {db_url}...")
# Simple retry logic
for i in range(10):
    try:
        # Use a synchronous engine just for the check
        engine = create_engine(db_url.replace("postgresql+asyncpg", "postgresql"))
        with engine.connect() as conn:
            print("Database is ready!")
            sys.exit(0)
    except Exception as e:
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
