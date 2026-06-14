"""
Worker Module.

Provides task worker that consumes tasks from queue and dispatches
to corresponding services for execution.
"""
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from backend.core.models import Task, TaskType, TaskStatus
from backend.core.logger import get_logger, TaskContext
from backend.workers.queue import (
    QueueManager,
    TaskEvent,
    InvalidStateTransitionError,
    TaskAlreadyRunningError,
)


# ============================================================================
# Types
# ============================================================================

# Progress callback: (progress: int) -> None
ProgressCallback = Callable[[int], None]

# Payload update callback: (payload_updates: Dict[str, Any]) -> None
PayloadUpdateCallback = Callable[[Dict[str, Any]], None]


class WorkerState(str, Enum):
    """Worker lifecycle states."""
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


# ============================================================================
# Service Interface
# ============================================================================

class BaseService(ABC):
    """
    Base class for all business services.
    
    All services must implement this interface to be compatible
    with the worker system.
    """
    
    @abstractmethod
    async def execute(
        self,
        task: Task,
        progress_callback: ProgressCallback,
        payload_callback: Optional['PayloadUpdateCallback'] = None,
    ) -> Dict[str, Any]:
        """
        Execute the task.
        
        Args:
            task: Task to execute
            progress_callback: Callback to report progress (0-100)
            payload_callback: Optional callback to update task payload
            
        Returns:
            Result dictionary to store in task.result
            
        Raises:
            Exception: On execution failure
        """
        pass
    
    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: ID of task to cancel
            
        Returns:
            True if cancellation was successful
        """
        return False
    
    def can_retry(self, error: Exception) -> bool:
        """
        Determine if error is retryable.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if task should be retried
        """
        # Default: retry on network/timeout errors
        error_str = str(error).lower()
        retryable_keywords = [
            "timeout", "connection", "network",
            "rate limit", "throttl", "temporary",
            "unavailable", "503", "429",
        ]
        return any(kw in error_str for kw in retryable_keywords)



# ============================================================================
# Worker
# ============================================================================

class Worker:
    """
    Task worker that consumes tasks from queue and executes them.
    
    Each worker handles a specific task type and ensures only one
    task of that type runs at a time.
    """
    
    def __init__(
        self,
        task_type: TaskType,
        queue_manager: QueueManager,
        service: BaseService,
        poll_interval: float = 1.0,
        progress_report_interval: float = 1.0,
        progress_report_threshold: int = 5,
    ):
        """
        Initialize worker.
        
        Args:
            task_type: Type of tasks this worker handles
            queue_manager: Queue manager instance
            service: Business service to execute tasks
            poll_interval: Interval between queue polls (seconds)
            progress_report_interval: Min interval between progress reports
            progress_report_threshold: Min progress change to trigger report
        """
        self._task_type = task_type
        self._queue = queue_manager
        self._service = service
        self._poll_interval = poll_interval
        self._progress_interval = progress_report_interval
        self._progress_threshold = progress_report_threshold
        
        self._state = WorkerState.IDLE
        self._current_task: Optional[Task] = None
        self._stop_event = asyncio.Event()
        self._logger = get_logger(f"worker.{task_type.value}")
        
        # Progress tracking
        self._last_progress = 0
        self._last_progress_time = datetime.min
    
    @property
    def task_type(self) -> TaskType:
        """Get worker's task type."""
        return self._task_type
    
    @property
    def state(self) -> WorkerState:
        """Get worker state."""
        return self._state
    
    @property
    def current_task(self) -> Optional[Task]:
        """Get currently executing task."""
        return self._current_task
    
    async def start(self) -> None:
        """Start the worker main loop."""
        if self._state != WorkerState.IDLE:
            self._logger.warning(f"Worker already in state: {self._state}")
            return
        
        self._state = WorkerState.RUNNING
        self._stop_event.clear()
        self._logger.info(f"Worker started for task type: {self._task_type.value}")
        
        try:
            await self._main_loop()
        finally:
            self._state = WorkerState.STOPPED
            self._logger.info(f"Worker stopped for task type: {self._task_type.value}")
    
    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the worker gracefully.
        
        Args:
            timeout: Max time to wait for current task to complete
        """
        if self._state != WorkerState.RUNNING:
            return
        
        self._state = WorkerState.STOPPING
        self._stop_event.set()
        self._logger.info(f"Stopping worker for {self._task_type.value}...")
        
        # Wait for current task to complete
        if self._current_task:
            self._logger.info(f"Waiting for task {self._current_task.id} to complete...")
            start = datetime.utcnow()
            while self._current_task and (datetime.utcnow() - start).total_seconds() < timeout:
                await asyncio.sleep(0.5)
            
            if self._current_task:
                self._logger.warning(f"Timeout waiting for task {self._current_task.id}")
    
    async def _main_loop(self) -> None:
        """Worker main loop."""
        while not self._stop_event.is_set():
            try:
                # Try to get a task
                task = await self._queue.dequeue(self._task_type)
                
                if task:
                    await self._execute_task(task)
                else:
                    # No task available, wait before next poll
                    await asyncio.sleep(self._poll_interval)
                    
            except Exception as e:
                self._logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(self._poll_interval)
    
    async def _execute_task(self, task: Task) -> None:
        """
        Execute a single task.
        
        Args:
            task: Task to execute
        """
        self._current_task = task
        self._last_progress = 0
        self._last_progress_time = datetime.min
        
        # Set up task context for logging
        video_id = task.video_id
        video_path = None
        if task.payload and "video_path" in task.payload:
            video_path = task.payload["video_path"]
        
        try:
            # Start task
            async with TaskContext(task.id, video_id, video_path):
                self._logger.info(f"Starting task: {task.id}")
                
                try:
                    await self._queue.start_task(task.id)
                except TaskAlreadyRunningError:
                    self._logger.warning(f"Task type already running, skipping: {task.id}")
                    return
                except InvalidStateTransitionError as e:
                    self._logger.warning(f"Invalid state transition: {e}")
                    return
                
                # Execute via service
                try:
                    result = await self._service.execute(
                        task,
                        self._create_progress_callback(task.id),
                        self._create_payload_callback(task.id),
                    )
                    
                    # Task completed successfully
                    await self._queue.complete_task(task.id, result)
                    self._logger.info(f"Task completed: {task.id}")
                    
                except Exception as e:
                    # Task failed
                    error_msg = str(e)
                    self._logger.error(f"Task failed: {task.id} - {error_msg}")
                    
                    await self._queue.fail_task(task.id, error_msg)
                    
                    # Check if retryable
                    if self._service.can_retry(e):
                        self._logger.info(f"Task {task.id} is retryable")
                    
        finally:
            self._current_task = None
    
    def _create_progress_callback(self, task_id: str) -> ProgressCallback:
        """Create progress callback for a task."""
        
        async def _update_progress(progress: int) -> None:
            """Async progress update."""
            now = datetime.utcnow()
            time_diff = (now - self._last_progress_time).total_seconds()
            progress_diff = abs(progress - self._last_progress)
            
            # Rate limit progress updates
            should_update = (
                time_diff >= self._progress_interval or
                progress_diff >= self._progress_threshold or
                progress == 100
            )
            
            if should_update:
                await self._queue.update_progress(task_id, progress)
                self._last_progress = progress
                self._last_progress_time = now
        
        def callback(progress: int) -> None:
            """Sync wrapper for progress callback."""
            # Schedule async update
            asyncio.create_task(_update_progress(progress))
        
        return callback
    
    def _create_payload_callback(self, task_id: str) -> 'PayloadUpdateCallback':
        """Create payload update callback for a task."""
        
        async def _update_payload(payload_updates: Dict[str, Any]) -> None:
            """Async payload update."""
            try:
                await self._queue.update_task_payload(task_id, payload_updates)
                self._logger.info(f"Task {task_id} payload updated: {list(payload_updates.keys())}")
                
                # Broadcast metadata update via WebSocket
                try:
                    from backend.app.routers.websocket import broadcast_task_metadata
                    await broadcast_task_metadata(task_id, payload_updates)
                except Exception as e:
                    self._logger.warning(f"Failed to broadcast metadata update: {e}")
                    
            except Exception as e:
                self._logger.error(f"Failed to update task payload: {e}")
        
        def callback(payload_updates: Dict[str, Any]) -> None:
            """Sync wrapper for payload callback."""
            # Schedule async update
            asyncio.create_task(_update_payload(payload_updates))
        
        return callback



# ============================================================================
# Worker Manager
# ============================================================================

class WorkerManager:
    """
    Manages all worker instances.
    
    Handles worker lifecycle, health monitoring, and graceful shutdown.
    """
    
    def __init__(
        self,
        queue_manager: QueueManager,
        poll_interval: float = 1.0,
        shutdown_timeout: float = 30.0,
    ):
        """
        Initialize worker manager.
        
        Args:
            queue_manager: Queue manager instance
            poll_interval: Default poll interval for workers
            shutdown_timeout: Timeout for graceful shutdown
        """
        self._queue = queue_manager
        self._poll_interval = poll_interval
        self._shutdown_timeout = shutdown_timeout
        
        self._workers: Dict[TaskType, Worker] = {}
        self._services: Dict[TaskType, BaseService] = {}
        self._tasks: Dict[TaskType, asyncio.Task] = {}
        self._running = False
        self._logger = get_logger("worker_manager")
    
    def register_service(self, task_type: TaskType, service: BaseService) -> None:
        """
        Register a service for a task type.
        
        Args:
            task_type: Task type the service handles
            service: Service instance
        """
        self._services[task_type] = service
        self._logger.info(f"Registered service for {task_type.value}")
    
    async def start(self, task_types: Optional[List[TaskType]] = None) -> None:
        """
        Start workers for specified task types.
        
        Args:
            task_types: List of task types to start workers for.
                       If None, starts workers for all registered services.
        """
        if self._running:
            self._logger.warning("WorkerManager already running")
            return
        
        self._running = True
        
        # Determine which workers to start
        types_to_start = task_types or list(self._services.keys())
        
        # Recover interrupted tasks first
        recovered = await self._queue.recover_interrupted_tasks()
        if recovered:
            self._logger.info(f"Recovered {len(recovered)} interrupted tasks")
        
        # Create and start workers
        for task_type in types_to_start:
            if task_type not in self._services:
                self._logger.warning(f"No service registered for {task_type.value}, skipping")
                continue
            
            worker = Worker(
                task_type=task_type,
                queue_manager=self._queue,
                service=self._services[task_type],
                poll_interval=self._poll_interval,
            )
            self._workers[task_type] = worker
            
            # Start worker as async task
            self._tasks[task_type] = asyncio.create_task(
                worker.start(),
                name=f"worker_{task_type.value}",
            )
        
        self._logger.info(f"Started {len(self._workers)} workers")
    
    async def stop(self) -> None:
        """Stop all workers gracefully."""
        if not self._running:
            return
        
        self._logger.info("Stopping all workers...")
        self._running = False
        
        # Signal all workers to stop
        stop_tasks = []
        for task_type, worker in self._workers.items():
            stop_tasks.append(worker.stop(self._shutdown_timeout))
        
        # Wait for all workers to stop
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Cancel any remaining tasks
        for task_type, task in self._tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._workers.clear()
        self._tasks.clear()
        self._logger.info("All workers stopped")
    
    def get_worker_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all workers.
        
        Returns:
            Dict mapping task type to worker status
        """
        status = {}
        for task_type, worker in self._workers.items():
            current_task = worker.current_task
            status[task_type.value] = {
                "state": worker.state.value,
                "current_task_id": current_task.id if current_task else None,
            }
        return status
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all workers.
        
        Returns:
            Dict mapping task type to health status
        """
        health = {}
        for task_type, task in self._tasks.items():
            # Worker is healthy if task is running and not done
            health[task_type.value] = not task.done()
        return health
