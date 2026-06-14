"""
Statistics API endpoints.

Provides REST API for dashboard statistics.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.app.schemas import success_response
from backend.app.deps import get_db
from backend.core import get_logger
from backend.core.models import Video, Task, TaskStatus


router = APIRouter(prefix="/stats", tags=["Statistics"])
logger = get_logger("api.stats")


@router.get("")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get dashboard statistics.
    
    Returns:
    - totalVideos: Total number of downloaded videos
    - runningTasks: Number of currently running tasks
    - completedToday: Number of tasks completed today
    """
    try:
        # Count total videos
        video_count_result = await db.execute(select(func.count(Video.id)))
        total_videos = video_count_result.scalar() or 0
        
        # Count running tasks
        running_count_result = await db.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.RUNNING)
        )
        running_tasks = running_count_result.scalar() or 0
        
        # Count tasks completed today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today_result = await db.execute(
            select(func.count(Task.id)).where(
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= today_start
            )
        )
        completed_today = completed_today_result.scalar() or 0
        
        return success_response(
            data={
                "totalVideos": total_videos,
                "runningTasks": running_tasks,
                "completedToday": completed_today,
            }
        )
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        return success_response(
            data={
                "totalVideos": 0,
                "runningTasks": 0,
                "completedToday": 0,
            }
        )
