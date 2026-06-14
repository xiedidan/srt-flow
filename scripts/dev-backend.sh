#!/bin/bash
# Development backend startup script with hot reload

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load PORT from .env file, default to 8031 if not found
PORT=8031
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep '^PORT=' | xargs)
fi

# Start backend with hot reload
echo "Starting backend on port ${PORT}..."
uvicorn backend.app.main:app \
    --reload \
    --reload-dir backend \
    --host 0.0.0.0 \
    --port ${PORT} \
    --log-level info
