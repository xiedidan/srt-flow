"""
Workers module for SRT Flow task scheduling.

This package contains task queue and worker components:
- queue: Queue manager for persistent task queue
- worker: Task worker process
- scheduler: Task scheduler
"""
from backend.workers.queue import (
    # Queue Manager
    QueueManager,
    get_queue_manager,
    # Events
    EventEmitter,
    TaskEvent,
    EventCallback,
    # Data Objects
    QueueStats,
    TaskFilter,
    # State Transitions
    VALID_TRANSITIONS,
    can_transition,
    # Exceptions
    QueueError,
    TaskNotFoundError,
    InvalidStateTransitionError,
    MaxRetriesExceededError,
    TaskAlreadyRunningError,
)

from backend.workers.worker import (
    # Worker
    Worker,
    WorkerManager,
    WorkerState,
    # Service Interface
    BaseService,
    ProgressCallback,
)

from backend.workers.scheduler import (
    # Scheduler
    Scheduler,
    SchedulerConfig,
    SchedulerEvent,
    SchedulerCallback,
    # Sub-components
    TimeWindowController,
    RetryScheduler,
    TimeoutDetector,
    PipelineOrchestrator,
    # Pipeline Rules
    PIPELINE_RULES,
)


__all__ = [
    # Queue Manager
    "QueueManager",
    "get_queue_manager",
    # Queue Events
    "EventEmitter",
    "TaskEvent",
    "EventCallback",
    # Queue Data Objects
    "QueueStats",
    "TaskFilter",
    # Queue State Transitions
    "VALID_TRANSITIONS",
    "can_transition",
    # Queue Exceptions
    "QueueError",
    "TaskNotFoundError",
    "InvalidStateTransitionError",
    "MaxRetriesExceededError",
    "TaskAlreadyRunningError",
    # Worker
    "Worker",
    "WorkerManager",
    "WorkerState",
    # Service Interface
    "BaseService",
    "ProgressCallback",
    # Scheduler
    "Scheduler",
    "SchedulerConfig",
    "SchedulerEvent",
    "SchedulerCallback",
    # Scheduler Sub-components
    "TimeWindowController",
    "RetryScheduler",
    "TimeoutDetector",
    "PipelineOrchestrator",
    # Pipeline Rules
    "PIPELINE_RULES",
]
