#!/bin/bash
# SRT Flow Entrypoint Script

set -e

# Print startup info
echo "=========================================="
echo "  SRT Flow - Starting..."
echo "=========================================="
echo "Python: $(python --version)"
echo "FFmpeg: $(ffmpeg -version 2>&1 | head -n1)"
echo "yt-dlp: $(yt-dlp --version)"
echo "=========================================="

# Create data directories if not exist
mkdir -p /app/data/downloads
mkdir -p /app/data/logs

# Check for GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo "=========================================="
fi

# Initialize database if needed
echo "Initializing database..."
python -c "
from backend.core.database import init_database
import asyncio
asyncio.run(init_database())
print('Database initialized.')
" 2>/dev/null || echo "Database initialization skipped (may already exist)"

echo "=========================================="
echo "  Starting server on port 8010..."
echo "=========================================="

# Execute the main command
exec "$@"
