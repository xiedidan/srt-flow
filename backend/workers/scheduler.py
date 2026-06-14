"""
Scheduler Module.

Provides task scheduling, retry management, time window control,
timeout detection, and pipeline orchestration.
"""
import asyncio
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from backend.core.models import Task, TaskType, TaskStatus, TaskPriority
from backend.core.logger import get_logger
from backend.workers.queue import (
    QueueManager,
    TaskEvent,
    TaskFilter,
    MaxRetriesExceededError,
)


# ============================================================================
# Configuration
# ============================================================================

class SchedulerConfig:
    """Scheduler configuration."""
    
    def __init__(
        self,
        retry_check_interval: int = 30,
        timeout_check_interval: int = 60,
        time_window_check_interval: int = 60,
        max_retries: int = 3,
        base_retry_interval: int = 60,
        max_retry_interval: int = 3600,
        retry_backoff_factor: float = 2.0,
    ):
        self.retry_check_interval = retry_check_interval
        self.timeout_check_interval = timeout_check_interval
        self.time_window_check_interval = time_window_check_interval
        self.max_retries = max_retries
        self.base_retry_interval = base_retry_interval
        self.max_retry_interval = max_retry_interval
        self.retry_backoff_factor = retry_backoff_factor
        
        # Task timeouts (seconds)
        self.task_timeouts: Dict[TaskType, int] = {
            TaskType.DOWNLOAD: 7200,      # 2 hours
            TaskType.ASR: 3600,           # 1 hour
            TaskType.TRANSLATE: 1800,     # 30 minutes
            TaskType.TTS: 3600,           # 1 hour
            TaskType.SYNTHESIZE: 3600,    # 1 hour
            TaskType.ASSET_GEN: 1800,     # 30 minutes
        }
        
        # Time windows: (start_time, end_time) or None for no restriction
        self.time_windows: Dict[TaskType, Optional[tuple]] = {
            TaskType.DOWNLOAD: None,
            TaskType.ASR: None,
            TaskType.TRANSLATE: None,
            TaskType.TTS: None,
            TaskType.SYNTHESIZE: None,
            TaskType.ASSET_GEN: None,
        }


# ============================================================================
# Pipeline Definition
# ============================================================================

# Pipeline: upstream -> list of downstream tasks
PIPELINE_RULES: Dict[TaskType, List[TaskType]] = {
    TaskType.DOWNLOAD: [TaskType.ASR],
    TaskType.ASR: [TaskType.TRANSLATE],
    TaskType.TRANSLATE: [TaskType.TTS, TaskType.ASSET_GEN],
    TaskType.TTS: [TaskType.SYNTHESIZE],
    TaskType.SYNTHESIZE: [],
    TaskType.ASSET_GEN: [],
}


# ============================================================================
# Scheduler Events
# ============================================================================

class SchedulerEvent(str, Enum):
    """Scheduler events."""
    RETRY_SCHEDULED = "scheduler.retry_scheduled"
    TASK_TIMEOUT = "scheduler.task_timeout"
    PIPELINE_TRIGGERED = "scheduler.pipeline_triggered"
    RECOVERY_COMPLETED = "scheduler.recovery_completed"


SchedulerCallback = Callable[[SchedulerEvent, Dict[str, Any]], None]


# ============================================================================
# Time Window Controller
# ============================================================================

class TimeWindowController:
    """Controls task execution based on time windows."""
    
    def __init__(self, config: SchedulerConfig):
        self._config = config
        self._logger = get_logger("scheduler.time_window")
    
    def is_in_time_window(self, task_type: TaskType) -> bool:
        """
        Check if current time is within allowed window for task type.
        
        Args:
            task_type: Task type to check
            
        Returns:
            True if task can execute now
        """
        window = self._config.time_windows.get(task_type)
        if window is None:
            return True  # No restriction
        
        start_time, end_time = window
        now = datetime.now().time()
        
        # Handle cross-midnight windows (e.g., 22:00 - 06:00)
        if start_time > end_time:
            return now >= start_time or now < end_time
        else:
            return start_time <= now < end_time
    
    def get_next_window_start(self, task_type: TaskType) -> Optional[datetime]:
        """
        Get next time window start for task type.
        
        Args:
            task_type: Task type
            
        Returns:
            Next window start datetime, or None if no restriction
        """
        window = self._config.time_windows.get(task_type)
        if window is None:
            return None
        
        start_time, end_time = window
        now = datetime.now()
        today_start = datetime.combine(now.date(), start_time)
        
        if self.is_in_time_window(task_type):
            return None  # Already in window
        
        # If start time is later today
        if now.time() < start_time:
            return today_start
        
        # Start time is tomorrow
        return today_start + timedelta(days=1)
    
    def set_time_window(
        self,
        task_type: TaskType,
        start_time: Optional[time],
        end_time: Optional[time],
    ) -> None:
        """
        Set time window for task type.
        
        Args:
            task_type: Task type
            start_time: Window start time (None to remove restriction)
            end_time: Window end time
        """
        if start_time is None or end_time is None:
            self._config.time_windows[task_type] = None
        else:
            self._config.time_windows[task_type] = (start_time, end_time)
        
        self._logger.info(
            f"Time window for {task_type.value}: "
            f"{start_time} - {end_time}" if start_time else "no restriction"
        )


# ============================================================================
# Retry Scheduler
# ============================================================================

class RetryScheduler:
    """Manages task retry scheduling with exponential backoff."""
    
    def __init__(self, config: SchedulerConfig, queue: QueueManager):
        self._config = config
        self._queue = queue
        self._logger = get_logger("scheduler.retry")
    
    def calculate_retry_delay(self, retry_count: int) -> int:
        """
        Calculate retry delay using exponential backoff.
        
        Args:
            retry_count: Current retry count
            
        Returns:
            Delay in seconds
        """
        delay = self._config.base_retry_interval * (
            self._config.retry_backoff_factor ** retry_count
        )
        return min(int(delay), self._config.max_retry_interval)
    
    async def schedule_retry(
        self,
        task: Task,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> bool:
        """
        Schedule a failed task for retry.
        
        Args:
            task: Failed task
            priority: Priority for retry (HIGH for queue jumping)
            
        Returns:
            True if retry was scheduled
        """
        if task.retry_count >= task.max_retries:
            self._logger.warning(
                f"Task {task.id} exceeded max retries ({task.max_retries})"
            )
            return False
        
        try:
            await self._queue.retry_task(task.id, priority)
            delay = self.calculate_retry_delay(task.retry_count)
            self._logger.info(
                f"Scheduled retry for task {task.id} "
                f"(attempt {task.retry_count + 1}/{task.max_retries}, "
                f"delay: {delay}s)"
            )
            return True
        except MaxRetriesExceededError:
            return False
        except Exception as e:
            self._logger.error(f"Failed to schedule retry for {task.id}: {e}")
            return False
    
    async def check_failed_tasks(self) -> List[Task]:
        """
        Check for failed tasks that need retry.
        
        Returns:
            List of tasks scheduled for retry
        """
        filters = TaskFilter(status=TaskStatus.FAILED)
        failed_tasks = await self._queue.get_tasks(filters, page_size=100)
        
        retried = []
        for task in failed_tasks:
            if task.retry_count < task.max_retries:
                if await self.schedule_retry(task):
                    retried.append(task)
        
        return retried



# ============================================================================
# Timeout Detector
# ============================================================================

class TimeoutDetector:
    """Detects and handles task timeouts."""
    
    def __init__(self, config: SchedulerConfig, queue: QueueManager):
        self._config = config
        self._queue = queue
        self._logger = get_logger("scheduler.timeout")
    
    def get_timeout(self, task_type: TaskType) -> int:
        """Get timeout for task type in seconds."""
        return self._config.task_timeouts.get(task_type, 3600)
    
    def is_timed_out(self, task: Task) -> bool:
        """
        Check if task has timed out.
        
        Args:
            task: Task to check
            
        Returns:
            True if task has exceeded timeout
        """
        if task.status != TaskStatus.RUNNING or not task.started_at:
            return False
        
        timeout = self.get_timeout(task.type)
        elapsed = (datetime.utcnow() - task.started_at).total_seconds()
        return elapsed > timeout
    
    async def check_timeouts(self) -> List[Task]:
        """
        Check for timed out tasks and mark them as failed.
        
        Returns:
            List of timed out tasks
        """
        running_tasks = await self._queue.get_running_tasks()
        timed_out = []
        
        for task in running_tasks:
            if self.is_timed_out(task):
                timeout = self.get_timeout(task.type)
                elapsed = (datetime.utcnow() - task.started_at).total_seconds()
                
                self._logger.warning(
                    f"Task {task.id} timed out "
                    f"(elapsed: {elapsed:.0f}s, timeout: {timeout}s)"
                )
                
                await self._queue.fail_task(
                    task.id,
                    f"Task timed out after {elapsed:.0f} seconds"
                )
                timed_out.append(task)
        
        return timed_out


# ============================================================================
# Pipeline Orchestrator
# ============================================================================

class PipelineOrchestrator:
    """Orchestrates pipeline task execution."""
    
    def __init__(self, queue: QueueManager):
        self._queue = queue
        self._logger = get_logger("scheduler.pipeline")
        
        # Track which tasks should trigger pipeline
        self._pipeline_enabled: Dict[str, bool] = {}
    
    def enable_pipeline(self, task_id: str, enabled: bool = True) -> None:
        """
        Enable/disable pipeline for a task.
        
        Args:
            task_id: Task ID
            enabled: Whether to trigger downstream tasks on completion
        """
        self._pipeline_enabled[task_id] = enabled
    
    def is_pipeline_enabled(self, task_id: str) -> bool:
        """Check if pipeline is enabled for task."""
        return self._pipeline_enabled.get(task_id, False)
    
    def get_downstream_tasks(self, task_type: TaskType) -> List[TaskType]:
        """Get downstream task types for a task type."""
        return PIPELINE_RULES.get(task_type, [])
    
    async def trigger_downstream(
        self,
        completed_task: Task,
        enabled_types: Optional[Set[TaskType]] = None,
    ) -> List[Task]:
        """
        Trigger downstream tasks after task completion.
        
        Args:
            completed_task: The completed task
            enabled_types: Set of task types to trigger (None for all)
            
        Returns:
            List of created downstream tasks
        """
        if not self.is_pipeline_enabled(completed_task.id):
            return []
        
        downstream_types = self.get_downstream_tasks(completed_task.type)
        if not downstream_types:
            return []
        
        created_tasks = []
        for task_type in downstream_types:
            if enabled_types and task_type not in enabled_types:
                continue
            
            # Create downstream task with same video_id
            task = await self._queue.enqueue(
                task_type=task_type,
                video_id=completed_task.video_id,
                payload={
                    "upstream_task_id": completed_task.id,
                    "upstream_result": completed_task.result,
                },
                priority=completed_task.priority,
            )
            
            # Enable pipeline for downstream task too
            self.enable_pipeline(task.id, True)
            created_tasks.append(task)
            
            self._logger.info(
                f"Triggered downstream task {task.id} ({task_type.value}) "
                f"from {completed_task.id}"
            )
        
        # Clean up
        del self._pipeline_enabled[completed_task.id]
        
        return created_tasks



# ============================================================================
# Scheduler
# ============================================================================

class Scheduler:
    """
    Main scheduler that coordinates all scheduling activities.
    
    Handles retry scheduling, timeout detection, time window control,
    and pipeline orchestration.
    """
    
    def __init__(
        self,
        queue_manager: QueueManager,
        config: Optional[SchedulerConfig] = None,
    ):
        """
        Initialize scheduler.
        
        Args:
            queue_manager: Queue manager instance
            config: Scheduler configuration
        """
        self._queue = queue_manager
        self._config = config or SchedulerConfig()
        self._logger = get_logger("scheduler")
        
        # Sub-components
        self._time_window = TimeWindowController(self._config)
        self._retry_scheduler = RetryScheduler(self._config, queue_manager)
        self._timeout_detector = TimeoutDetector(self._config, queue_manager)
        self._pipeline = PipelineOrchestrator(queue_manager)
        
        # State
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._callbacks: List[SchedulerCallback] = []
        
        # Subscribe to queue events
        self._queue.events.on(TaskEvent.COMPLETED, self._on_task_completed)
        self._queue.events.on(TaskEvent.FAILED, self._on_task_failed)
    
    @property
    def time_window(self) -> TimeWindowController:
        """Get time window controller."""
        return self._time_window
    
    @property
    def pipeline(self) -> PipelineOrchestrator:
        """Get pipeline orchestrator."""
        return self._pipeline
    
    def on_event(self, callback: SchedulerCallback) -> None:
        """Register event callback."""
        self._callbacks.append(callback)
    
    def _emit_event(self, event: SchedulerEvent, data: Dict[str, Any]) -> None:
        """Emit scheduler event."""
        for callback in self._callbacks:
            try:
                callback(event, data)
            except Exception as e:
                self._logger.error(f"Event callback error: {e}")
    
    async def start(self) -> None:
        """Start scheduler background tasks."""
        if self._running:
            self._logger.warning("Scheduler already running")
            return
        
        self._running = True
        self._logger.info("Starting scheduler...")
        
        # Start periodic tasks
        self._tasks = [
            asyncio.create_task(
                self._retry_check_loop(),
                name="scheduler_retry_check",
            ),
            asyncio.create_task(
                self._timeout_check_loop(),
                name="scheduler_timeout_check",
            ),
        ]
        
        self._logger.info("Scheduler started")
    
    async def stop(self) -> None:
        """Stop scheduler."""
        if not self._running:
            return
        
        self._running = False
        self._logger.info("Stopping scheduler...")
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self._logger.info("Scheduler stopped")
    
    async def _retry_check_loop(self) -> None:
        """Periodic retry check loop."""
        while self._running:
            try:
                retried = await self._retry_scheduler.check_failed_tasks()
                if retried:
                    self._emit_event(SchedulerEvent.RETRY_SCHEDULED, {
                        "count": len(retried),
                        "task_ids": [t.id for t in retried],
                    })
            except Exception as e:
                self._logger.error(f"Retry check error: {e}")
            
            await asyncio.sleep(self._config.retry_check_interval)
    
    async def _timeout_check_loop(self) -> None:
        """Periodic timeout check loop."""
        while self._running:
            try:
                timed_out = await self._timeout_detector.check_timeouts()
                for task in timed_out:
                    self._emit_event(SchedulerEvent.TASK_TIMEOUT, {
                        "task_id": task.id,
                        "task_type": task.type.value,
                    })
            except Exception as e:
                self._logger.error(f"Timeout check error: {e}")
            
            await asyncio.sleep(self._config.timeout_check_interval)
    
    def _on_task_completed(
        self,
        event: TaskEvent,
        task_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Handle task completion event."""
        # Schedule pipeline trigger as async task
        asyncio.create_task(self._trigger_pipeline(task_id))
    
    def _on_task_failed(
        self,
        event: TaskEvent,
        task_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Handle task failure event."""
        # Retry scheduling is handled by periodic check
        pass
    
    async def _trigger_pipeline(self, task_id: str) -> None:
        """Trigger pipeline for completed task."""
        try:
            task = await self._queue.get_task(task_id)
            if task and task.status == TaskStatus.COMPLETED:
                created = await self._pipeline.trigger_downstream(task)
                if created:
                    self._emit_event(SchedulerEvent.PIPELINE_TRIGGERED, {
                        "upstream_task_id": task_id,
                        "downstream_task_ids": [t.id for t in created],
                    })
        except Exception as e:
            self._logger.error(f"Pipeline trigger error for {task_id}: {e}")
    
    def can_execute_now(self, task_type: TaskType) -> bool:
        """
        Check if task type can execute now (time window check).
        
        Args:
            task_type: Task type to check
            
        Returns:
            True if task can execute
        """
        return self._time_window.is_in_time_window(task_type)
    
    async def schedule_retry(
        self,
        task_id: str,
        priority: TaskPriority = TaskPriority.HIGH,
    ) -> bool:
        """
        Manually schedule a retry for a failed task.
        
        Args:
            task_id: Task ID
            priority: Priority for retry
            
        Returns:
            True if retry was scheduled
        """
        task = await self._queue.get_task(task_id)
        if not task or task.status != TaskStatus.FAILED:
            return False
        
        return await self._retry_scheduler.schedule_retry(task, priority)
