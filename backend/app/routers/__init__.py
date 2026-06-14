"""
API routers package.
"""
from fastapi import APIRouter

from backend.app.routers import health, config, tasks, videos, websocket, asr, ai_providers, stats, reference_audio, tts, system

# Create main API router with /api/v1 prefix
api_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(config.router)
api_router.include_router(tasks.router)
api_router.include_router(videos.router)
api_router.include_router(asr.router)
api_router.include_router(ai_providers.router)
api_router.include_router(stats.router)
api_router.include_router(reference_audio.router)
api_router.include_router(tts.router)
api_router.include_router(system.router)

# WebSocket router (no prefix, mounted at root level)
ws_router = websocket.router
