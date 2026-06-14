"""
Task management API endpoints.

Provides REST API for submitting, querying, and managing tasks.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas import success_response
from backend.app.deps import get_db
from backend.core import get_logger
from backend.core.models import TaskStatus


router = APIRouter(prefix="/tasks", tags=["Tasks"])
logger = get_logger("api.tasks")


# ============================================================================
# Request/Response Schemas
# ============================================================================

class TaskSubmitRequest(BaseModel):
    """Request body for submitting a new task."""
    type: str = Field(..., description="Task type: download, asr, translate, tts, synthesize, asset_gen, editor")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task-specific payload")
    group_id: Optional[str] = Field(None, description="Optional group ID for batch tasks")
    priority: int = Field(default=100, ge=1, le=1000, description="Task priority (lower = higher)")


class TaskActionRequest(BaseModel):
    """Request body for task actions."""
    action: str = Field(..., description="Action: retry, cancel")
    priority: Optional[str] = Field(None, description="Priority for retry: high (queue front), normal")


class TaskResponse(BaseModel):
    """Task response model."""
    id: str
    type: str
    status: str
    progress: int
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    video_id: Optional[str] = None
    video_title: Optional[str] = None
    group_id: Optional[str] = None


class TaskListResponse(BaseModel):
    """Task list response model."""
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# Endpoints
# ============================================================================

@router.post("")
async def submit_task(
    request: TaskSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a new processing task.
    
    Task types:
    - download: Download video from URL
    - asr: Speech recognition
    - translate: Subtitle translation
    - tts: Text-to-speech synthesis
    - synthesize: Video synthesis
    - asset_gen: Asset generation
    - editor: Video editing
    """
    from backend.core.repositories import TaskRepository
    
    try:
        # Create task in database
        from backend.core.models import Task, TaskType, TaskStatus, TaskPriority
        import uuid
        
        # Map string type to enum
        task_type_map = {
            'download': TaskType.DOWNLOAD,
            'asr': TaskType.ASR,
            'translate': TaskType.TRANSLATE,
            'tts': TaskType.TTS,
            'synthesize': TaskType.SYNTHESIZE,
            'asset_gen': TaskType.ASSET_GEN,
            'editor': TaskType.EDITOR,
        }
        
        if request.type not in task_type_map:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task type: {request.type}"
            )
        
        # Log download config when creating download task
        if request.type == 'download':
            from backend.core import get_config_manager
            config_mgr = get_config_manager()
            config_mgr.set_db_session(db)
            try:
                download_cfg = await config_mgr.get_config("download")
                cookies_browser = getattr(download_cfg, 'cookies_browser', None)
                logger.info(f"[POST /tasks] Creating download task, current config: cookies_browser={cookies_browser}")
            except Exception as e:
                logger.warning(f"[POST /tasks] Failed to read download config: {e}")
        
        # Determine priority
        if request.priority <= 50:
            priority = TaskPriority.HIGH
        elif request.priority <= 150:
            priority = TaskPriority.NORMAL
        else:
            priority = TaskPriority.LOW
        
        # Create task entity
        from datetime import datetime
        
        new_task_id = str(uuid.uuid4())
        new_task_type = task_type_map[request.type]
        
        logger.info(f"Creating task with type: {new_task_type}, id: {new_task_id}")
        
        # Create Task instance directly
        new_task = Task(
            id=new_task_id,
            video_id=request.payload.get('video_id'),
            type=new_task_type,
            status=TaskStatus.PENDING,
            progress=0,
            priority=priority,
            payload=request.payload,
            result=None,
            error=None,
            retry_count=0,
            max_retries=3,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
        )
        
        repo = TaskRepository(db)
        created_task = await repo.create(new_task)
        await db.commit()
        
        logger.info(f"Task submitted: {created_task.id} ({request.type})")
        
        return success_response(
            data={
                "id": created_task.id,
                "type": created_task.type.value,
                "status": created_task.status.value,
                "created_at": created_task.created_at.isoformat() if created_task.created_at else None,
            },
            message="Task submitted successfully"
        )
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}"
        )


@router.get("")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    type: Optional[str] = Query(None, description="Filter by task type"),
    video_id: Optional[str] = Query(None, description="Filter by video ID"),
    tag: Optional[str] = Query(None, description="Filter by video tag name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get task list with optional filters.
    
    Supports filtering by status, type, video_id, and tag.
    Results are paginated.
    """
    from backend.core.repositories import TaskRepository
    
    try:
        repo = TaskRepository(db)
        
        # Build filters
        filters = {}
        if status:
            filters["status"] = TaskStatus(status)
        if type:
            filters["task_type"] = type
        if video_id:
            filters["video_id"] = video_id
        if tag:
            filters["tag"] = tag
        
        # Get tasks with pagination
        tasks, total = await repo.list_with_pagination(
            filters=filters,
            page=page,
            page_size=page_size,
        )
        
        items = [
            TaskResponse(
                id=t.id,
                type=t.type.value if hasattr(t.type, 'value') else t.type,
                status=t.status.value,
                progress=t.progress or 0,
                payload=t.payload,
                result=t.result,
                error=t.error,
                created_at=t.created_at.isoformat() if t.created_at else None,
                started_at=t.started_at.isoformat() if t.started_at else None,
                completed_at=t.completed_at.isoformat() if t.completed_at else None,
                video_id=t.video_id,
                video_title=t.video.title if t.video else None,
            )
            for t in tasks
        ]
        
        return success_response(
            data={
                "items": [item.model_dump() for item in items],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid filter value: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get task details by ID.
    
    Returns task status, progress, result, and error information.
    """
    from backend.core.repositories import TaskRepository
    
    try:
        repo = TaskRepository(db)
        task = await repo.get_by_id(task_id)
        
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}"
            )
        
        return success_response(
            data={
                "id": task.id,
                "type": task.type.value if hasattr(task.type, 'value') else task.type,
                "status": task.status.value,
                "progress": task.progress or 0,
                "payload": task.payload,
                "result": task.result,
                "error": task.error,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "video_id": task.video_id,
                "retry_count": task.retry_count,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task: {str(e)}"
        )


@router.post("/{task_id}/action")
async def task_action(
    task_id: str,
    action_request: TaskActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Perform action on a task.
    
    Actions:
    - retry: Retry a failed task
    - cancel: Cancel a pending or running task
    """
    from backend.core.repositories import TaskRepository
    from backend.workers.queue import QueueManager
    
    try:
        repo = TaskRepository(db)
        task = await repo.get_by_id(task_id)
        
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}"
            )
        
        action = action_request.action.lower()
        
        if action == "retry":
            # Only failed tasks can be retried
            if task.status != TaskStatus.FAILED:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot retry task with status: {task.status.value}"
                )
            
            # Reset task status
            task.status = TaskStatus.PENDING
            task.error = None
            task.progress = 0
            task.started_at = None
            task.completed_at = None
            await repo.update(task)
            await db.commit()
            
            logger.info(f"Task {task_id} queued for retry")
            
            return success_response(
                data={"id": task_id, "status": "pending"},
                message="Task queued for retry"
            )
        
        elif action == "cancel":
            # Only pending or running tasks can be cancelled
            if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot cancel task with status: {task.status.value}"
                )
            
            # If task is running, try to cancel it via service
            if task.status == TaskStatus.RUNNING:
                # Import app to access services
                from backend.app.main import app
                
                # Get services from app state
                services = getattr(app.state, 'services', {})
                
                # Find the service for this task type
                service = services.get(task.type)
                if service:
                    try:
                        # Call service's cancel method
                        cancelled = await service.cancel(task_id)
                        if cancelled:
                            logger.info(f"Service cancelled task: {task_id}")
                        else:
                            logger.warning(f"Service could not cancel task: {task_id}")
                    except Exception as e:
                        logger.error(f"Error calling service cancel: {e}")
                else:
                    logger.warning(f"No service found for task type: {task.type.value}")
            
            # Update task status
            task.status = TaskStatus.FAILED
            task.error = "Cancelled by user"
            await repo.update(task)
            await db.commit()
            
            logger.info(f"Task {task_id} cancelled")
            
            return success_response(
                data={"id": task_id, "status": "failed"},
                message="Task cancelled"
            )
        
        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {action}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform action on task {task_id}: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform action: {str(e)}"
        )

