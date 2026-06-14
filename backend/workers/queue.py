"""
Queue Manager Module.

Provides SQLite-based persistent task queue management with priority scheduling,
state management, and concurrency control.
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum

from sqlalchemy import case, select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Task, TaskType, TaskStatus, TaskPriority, generate_uuid
from backend.core.exceptions import EntityNotFoundError
from backend.core.logger import get_logger


# ============================================================================
# Exceptions
# ============================================================================

class QueueError(Exception):
    """Base exception for queue operations."""
    pass


class TaskNotFoundError(QueueError):
    """Raised when task is not found."""
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class InvalidStateTransitionError(QueueError):
    """Raised when state transition is invalid."""
    def __init__(self, task_id: str, from_status: TaskStatus, to_status: TaskStatus):
        self.task_id = task_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid state transition for task {task_id}: "
            f"{from_status.value} -> {to_status.value}"
        )


class MaxRetriesExceededError(QueueError):
    """Raised when max retries exceeded."""
    def __init__(self, task_id: str, retry_count: int, max_retries: int):
        self.task_id = task_id
        self.retry_count = retry_count
        self.max_retries = max_retries
        super().__init__(
            f"Task {task_id} exceeded max retries: {retry_count}/{max_retries}"
        )


class TaskAlreadyRunningError(QueueError):
    """Raised when task type already has running task."""
    def __init__(self, task_type: TaskType):
        self.task_type = task_type
        super().__init__(f"Task type {task_type.value} already has a running task")


# ============================================================================
# State Transition Rules
# ============================================================================

VALID_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.PENDING},  # Retry
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    """Check if state transition is valid."""
    return to_status in VALID_TRANSITIONS.get(from_status, set())


# ============================================================================
# Data Transfer Objects
# ============================================================================

class QueueStats:
    """Queue statistics."""
    
    def __init__(
        self,
        total: int = 0,
        pending: int = 0,
        running: int = 0,
        completed: int = 0,
        failed: int = 0,
        cancelled: int = 0,
        by_type: Optional[Dict[str, Dict[str, int]]] = None,
    ):
        self.total = total
        self.pending = pending
        self.running = running
        self.completed = completed
        self.failed = failed
        self.cancelled = cancelled
        self.by_type = by_type or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "pending": self.pending,
            "running": self.running,
            "completed": self.completed,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "by_type": self.by_type,
        }


class TaskFilter:
    """Task query filter."""
    
    def __init__(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        video_id: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        self.status = status
        self.task_type = task_type
        self.video_id = video_id
        self.created_after = created_after
        self.created_before = created_before


# ============================================================================
# Event System
# ============================================================================

class TaskEvent(str, Enum):
    """Task lifecycle events."""
    CREATED = "task.created"
    STARTED = "task.started"
    PROGRESS = "task.progress"
    COMPLETED = "task.completed"
    FAILED = "task.failed"
    CANCELLED = "task.cancelled"


# Event callback type: (event, task_id, data) -> None
EventCallback = Callable[[TaskEvent, str, Dict[str, Any]], None]


class EventEmitter:
    """Simple event emitter for task events."""
    
    def __init__(self):
        self._listeners: Dict[TaskEvent, List[EventCallback]] = {}
    
    def on(self, event: TaskEvent, callback: EventCallback) -> None:
        """Register event listener."""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)
    
    def off(self, event: TaskEvent, callback: EventCallback) -> None:
        """Remove event listener."""
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb != callback
            ]
    
    def emit(self, event: TaskEvent, task_id: str, data: Dict[str, Any]) -> None:
        """Emit event to all listeners."""
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    callback(event, task_id, data)
                except Exception as e:
                    # Log but don't propagate listener errors
                    logger = get_logger(__name__)
                    logger.error(f"Event listener error: {e}")


# ============================================================================
# Queue Manager
# ============================================================================

class QueueManager:
    """
    Manages SQLite-based persistent task queue.
    
    Provides task enqueue, dequeue, status management, priority scheduling,
    and concurrency control.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize queue manager.
        
        Args:
            session: Database session
        """
        self._session = session
        self._events = EventEmitter()
        self._logger = get_logger(__name__)
    
    @property
    def events(self) -> EventEmitter:
        """Get event emitter for subscribing to task events."""
        return self._events
    
    # ========================================================================
    # Core Operations
    # ========================================================================
    
    async def enqueue(
        self,
        task_type: TaskType,
        video_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
    ) -> Task:
        """
        Add a new task to the queue.
        
        Args:
            task_type: Type of task
            video_id: Associated video ID (optional)
            payload: Task parameters
            priority: Task priority (high/normal/low)
            max_retries: Maximum retry attempts
            
        Returns:
            Created task
        """
        task = Task(
            id=generate_uuid(),
            type=task_type,
            video_id=video_id,
            payload=payload or {},
            priority=priority,
            status=TaskStatus.PENDING,
            progress=0,
            retry_count=0,
            max_retries=max_retries,
        )
        
        self._session.add(task)
        await self._session.flush()
        await self._session.refresh(task)
        
        self._logger.info(
            f"Task enqueued: {task.id} type={task_type.value} priority={priority.value}"
        )
        
        # Emit event
        self._events.emit(TaskEvent.CREATED, task.id, {
            "type": task_type.value,
            "video_id": video_id,
            "priority": priority.value,
        })
        
        return task
    
    async def dequeue(
        self,
        task_type: Optional[TaskType] = None,
    ) -> Optional[Task]:
        """
        Get next pending task from queue.
        
        Respects priority ordering and concurrency limits.
        Each task type can only have one running task at a time.
        
        Args:
            task_type: Filter by task type (optional)
            
        Returns:
            Next pending task, or None if queue is empty
        """
        # Check concurrency limit for task type
        if task_type:
            if not await self._can_start_task(task_type):
                return None
        else:
            # Find a task type that can run
            running_types = await self._get_running_task_types()
            # We'll filter out types that already have running tasks
        
        # Priority ordering: high=1, normal=2, low=3
        priority_order = case(
            (Task.priority == TaskPriority.HIGH, 1),
            (Task.priority == TaskPriority.NORMAL, 2),
            (Task.priority == TaskPriority.LOW, 3),
        )
        
        # Build query for pending tasks
        stmt = select(Task).where(Task.status == TaskStatus.PENDING)
        
        if task_type:
            stmt = stmt.where(Task.type == task_type)
        else:
            # Exclude types that already have running tasks
            running_types = await self._get_running_task_types()
            if running_types:
                stmt = stmt.where(~Task.type.in_(running_types))
        
        stmt = stmt.order_by(priority_order, Task.created_at.asc()).limit(1)
        
        result = await self._session.execute(stmt)
        task = result.scalar_one_or_none()
        
        return task

    
    async def start_task(self, task_id: str) -> Task:
        """
        Mark task as running.
        
        Args:
            task_id: Task ID
            
        Returns:
            Updated task
            
        Raises:
            TaskNotFoundError: If task not found
            InvalidStateTransitionError: If transition is invalid
            TaskAlreadyRunningError: If task type already has running task
        """
        task = await self._get_task_or_raise(task_id)
        
        # Validate state transition
        if not can_transition(task.status, TaskStatus.RUNNING):
            raise InvalidStateTransitionError(task_id, task.status, TaskStatus.RUNNING)
        
        # Check concurrency limit
        if not await self._can_start_task(task.type):
            raise TaskAlreadyRunningError(task.type)
        
        # Update task
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        await self._session.flush()
        
        self._logger.info(f"Task started: {task_id}")
        
        # Emit event
        self._events.emit(TaskEvent.STARTED, task_id, {
            "type": task.type.value,
        })
        
        return task
    
    async def update_progress(self, task_id: str, progress: int) -> Task:
        """
        Update task progress.
        
        Args:
            task_id: Task ID
            progress: Progress value (0-100)
            
        Returns:
            Updated task
        """
        task = await self._get_task_or_raise(task_id)
        
        # Clamp progress to valid range
        progress = max(0, min(100, progress))
        task.progress = progress
        
        await self._session.flush()
        
        # Emit event
        self._events.emit(TaskEvent.PROGRESS, task_id, {
            "progress": progress,
        })
        
        return task
    
    async def update_task_payload(self, task_id: str, payload_updates: Dict[str, Any]) -> Task:
        """
        Update task payload with new data.
        
        Merges payload_updates into existing payload.
        
        Args:
            task_id: Task ID
            payload_updates: Dict of payload fields to update
            
        Returns:
            Updated task
        """
        task = await self._get_task_or_raise(task_id)
        
        # Merge updates into existing payload
        if task.payload is None:
            task.payload = {}
        task.payload.update(payload_updates)
        
        await self._session.flush()
        
        self._logger.debug(f"Task {task_id} payload updated: {list(payload_updates.keys())}")
        
        return task
    
    async def complete_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Mark task as completed.
        
        Args:
            task_id: Task ID
            result: Task result data
            
        Returns:
            Updated task
        """
        task = await self._get_task_or_raise(task_id)
        
        if not can_transition(task.status, TaskStatus.COMPLETED):
            raise InvalidStateTransitionError(task_id, task.status, TaskStatus.COMPLETED)
        
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.result = result
        task.completed_at = datetime.utcnow()
        
        await self._session.flush()
        
        self._logger.info(f"Task completed: {task_id}")
        
        # Emit event
        self._events.emit(TaskEvent.COMPLETED, task_id, {
            "result": result,
        })
        
        return task
    
    async def fail_task(
        self,
        task_id: str,
        error: str,
    ) -> Task:
        """
        Mark task as failed.
        
        Args:
            task_id: Task ID
            error: Error message
            
        Returns:
            Updated task
        """
        task = await self._get_task_or_raise(task_id)
        
        if not can_transition(task.status, TaskStatus.FAILED):
            raise InvalidStateTransitionError(task_id, task.status, TaskStatus.FAILED)
        
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.utcnow()
        
        await self._session.flush()
        
        self._logger.warning(f"Task failed: {task_id} - {error}")
        
        # Emit event
        self._events.emit(TaskEvent.FAILED, task_id, {
            "error": error,
        })
        
        return task
    
    async def cancel_task(self, task_id: str) -> Task:
        """
        Cancel a pending or running task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Updated task
        """
        task = await self._get_task_or_raise(task_id)
        
        if not can_transition(task.status, TaskStatus.CANCELLED):
            raise InvalidStateTransitionError(task_id, task.status, TaskStatus.CANCELLED)
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        
        await self._session.flush()
        
        self._logger.info(f"Task cancelled: {task_id}")
        
        # Emit event
        self._events.emit(TaskEvent.CANCELLED, task_id, {})
        
        return task
    
    async def retry_task(
        self,
        task_id: str,
        priority: Optional[TaskPriority] = None,
    ) -> Task:
        """
        Retry a failed task.
        
        Args:
            task_id: Task ID
            priority: New priority (optional, defaults to HIGH for queue jumping)
            
        Returns:
            Updated task
            
        Raises:
            MaxRetriesExceededError: If max retries exceeded
        """
        task = await self._get_task_or_raise(task_id)
        
        if not can_transition(task.status, TaskStatus.PENDING):
            raise InvalidStateTransitionError(task_id, task.status, TaskStatus.PENDING)
        
        # Check retry limit
        if task.retry_count >= task.max_retries:
            raise MaxRetriesExceededError(task_id, task.retry_count, task.max_retries)
        
        # Update task
        task.status = TaskStatus.PENDING
        task.retry_count += 1
        task.error = None
        task.started_at = None
        task.completed_at = None
        
        if priority:
            task.priority = priority
        
        await self._session.flush()
        
        self._logger.info(
            f"Task retry scheduled: {task_id} (attempt {task.retry_count}/{task.max_retries})"
        )
        
        # Emit created event (re-entering queue)
        self._events.emit(TaskEvent.CREATED, task_id, {
            "type": task.type.value,
            "retry_count": task.retry_count,
        })
        
        return task

    
    # ========================================================================
    # Query Operations
    # ========================================================================
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None if not found
        """
        return await self._session.get(Task, task_id)
    
    async def get_tasks(
        self,
        filters: Optional[TaskFilter] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Task]:
        """
        Query tasks with filters and pagination.
        
        Args:
            filters: Query filters
            page: Page number (1-based)
            page_size: Items per page
            
        Returns:
            List of tasks
        """
        stmt = select(Task)
        
        if filters:
            if filters.status:
                stmt = stmt.where(Task.status == filters.status)
            if filters.task_type:
                stmt = stmt.where(Task.type == filters.task_type)
            if filters.video_id:
                stmt = stmt.where(Task.video_id == filters.video_id)
            if filters.created_after:
                stmt = stmt.where(Task.created_at >= filters.created_after)
            if filters.created_before:
                stmt = stmt.where(Task.created_at <= filters.created_before)
        
        # Order by created_at descending
        stmt = stmt.order_by(Task.created_at.desc())
        
        # Pagination
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def count_tasks(self, filters: Optional[TaskFilter] = None) -> int:
        """
        Count tasks matching filters.
        
        Args:
            filters: Query filters
            
        Returns:
            Task count
        """
        stmt = select(func.count(Task.id))
        
        if filters:
            if filters.status:
                stmt = stmt.where(Task.status == filters.status)
            if filters.task_type:
                stmt = stmt.where(Task.type == filters.task_type)
            if filters.video_id:
                stmt = stmt.where(Task.video_id == filters.video_id)
            if filters.created_after:
                stmt = stmt.where(Task.created_at >= filters.created_after)
            if filters.created_before:
                stmt = stmt.where(Task.created_at <= filters.created_before)
        
        result = await self._session.execute(stmt)
        return result.scalar() or 0
    
    async def get_queue_stats(self) -> QueueStats:
        """
        Get queue statistics.
        
        Returns:
            Queue statistics including counts by status and type
        """
        # Count by status
        status_stmt = select(
            Task.status, func.count(Task.id)
        ).group_by(Task.status)
        status_result = await self._session.execute(status_stmt)
        status_counts = {row[0].value: row[1] for row in status_result.all()}
        
        # Count by type and status
        type_stmt = select(
            Task.type, Task.status, func.count(Task.id)
        ).group_by(Task.type, Task.status)
        type_result = await self._session.execute(type_stmt)
        
        by_type: Dict[str, Dict[str, int]] = {}
        for row in type_result.all():
            task_type = row[0].value
            status = row[1].value
            count = row[2]
            if task_type not in by_type:
                by_type[task_type] = {}
            by_type[task_type][status] = count
        
        return QueueStats(
            total=sum(status_counts.values()),
            pending=status_counts.get("pending", 0),
            running=status_counts.get("running", 0),
            completed=status_counts.get("completed", 0),
            failed=status_counts.get("failed", 0),
            cancelled=status_counts.get("cancelled", 0),
            by_type=by_type,
        )
    
    async def get_tasks_by_video(self, video_id: str) -> List[Task]:
        """
        Get all tasks for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            List of tasks ordered by creation time
        """
        stmt = select(Task).where(
            Task.video_id == video_id
        ).order_by(Task.created_at.desc())
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_running_tasks(self) -> List[Task]:
        """
        Get all currently running tasks.
        
        Returns:
            List of running tasks
        """
        stmt = select(Task).where(Task.status == TaskStatus.RUNNING)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    # ========================================================================
    # Recovery Operations
    # ========================================================================
    
    async def recover_interrupted_tasks(self) -> List[Task]:
        """
        Recover tasks that were interrupted (e.g., by system restart).
        
        Finds tasks in RUNNING state and resets them to PENDING or FAILED
        based on retry count.
        
        Returns:
            List of recovered tasks
        """
        stmt = select(Task).where(Task.status == TaskStatus.RUNNING)
        result = await self._session.execute(stmt)
        running_tasks = list(result.scalars().all())
        
        recovered = []
        for task in running_tasks:
            if task.retry_count < task.max_retries:
                # Reset to pending for retry
                task.status = TaskStatus.PENDING
                task.retry_count += 1
                task.error = "Task interrupted, auto-retry scheduled"
                task.started_at = None
                self._logger.warning(
                    f"Recovered interrupted task: {task.id} -> pending "
                    f"(retry {task.retry_count}/{task.max_retries})"
                )
            else:
                # Mark as failed if max retries exceeded
                task.status = TaskStatus.FAILED
                task.error = "Task interrupted, max retries exceeded"
                task.completed_at = datetime.utcnow()
                self._logger.error(
                    f"Interrupted task failed: {task.id} (max retries exceeded)"
                )
            recovered.append(task)
        
        await self._session.flush()
        return recovered
    
    # ========================================================================
    # Batch Operations
    # ========================================================================
    
    async def enqueue_batch(
        self,
        tasks: List[Dict[str, Any]],
    ) -> List[Task]:
        """
        Enqueue multiple tasks at once.
        
        Args:
            tasks: List of task definitions with keys:
                - type: TaskType
                - video_id: Optional[str]
                - payload: Optional[Dict]
                - priority: Optional[TaskPriority]
                
        Returns:
            List of created tasks
        """
        created_tasks = []
        for task_def in tasks:
            task = await self.enqueue(
                task_type=task_def["type"],
                video_id=task_def.get("video_id"),
                payload=task_def.get("payload"),
                priority=task_def.get("priority", TaskPriority.NORMAL),
            )
            created_tasks.append(task)
        
        return created_tasks
    
    async def cancel_pending_by_video(self, video_id: str) -> int:
        """
        Cancel all pending tasks for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            Number of cancelled tasks
        """
        stmt = select(Task).where(
            Task.video_id == video_id,
            Task.status == TaskStatus.PENDING,
        )
        result = await self._session.execute(stmt)
        tasks = list(result.scalars().all())
        
        for task in tasks:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            self._events.emit(TaskEvent.CANCELLED, task.id, {})
        
        await self._session.flush()
        
        if tasks:
            self._logger.info(f"Cancelled {len(tasks)} pending tasks for video {video_id}")
        
        return len(tasks)
    
    # ========================================================================
    # Private Helpers
    # ========================================================================
    
    async def _get_task_or_raise(self, task_id: str) -> Task:
        """Get task by ID or raise exception."""
        task = await self._session.get(Task, task_id)
        if not task:
            raise TaskNotFoundError(task_id)
        return task
    
    async def _can_start_task(self, task_type: TaskType) -> bool:
        """Check if a task of given type can be started (concurrency limit)."""
        stmt = select(Task).where(
            Task.type == task_type,
            Task.status == TaskStatus.RUNNING,
        )
        result = await self._session.execute(stmt)
        running_task = result.scalar_one_or_none()
        return running_task is None
    
    async def _get_running_task_types(self) -> List[TaskType]:
        """Get list of task types that have running tasks."""
        stmt = select(Task.type).where(
            Task.status == TaskStatus.RUNNING
        ).distinct()
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]


# ============================================================================
# Factory Function
# ============================================================================

def get_queue_manager(session: AsyncSession) -> QueueManager:
    """
    Create a QueueManager instance.
    
    Args:
        session: Database session
        
    Returns:
        QueueManager instance
    """
    return QueueManager(session)
