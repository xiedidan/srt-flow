"""
Logger Manager Module.

Provides unified logging for SRT Flow with:
- Console output with color support
- File logging with rotation
- Task-specific log file routing
- Context-aware logging (task_id, video_id)
"""
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

# Context variables for task logging
current_task_id: ContextVar[Optional[str]] = ContextVar("current_task_id", default=None)
current_video_id: ContextVar[Optional[str]] = ContextVar("current_video_id", default=None)
current_video_path: ContextVar[Optional[str]] = ContextVar("current_video_path", default=None)


# ============================================================================
# Color Support
# ============================================================================

class Colors:
    """ANSI color codes for console output."""
    RESET = "\033[0m"
    GRAY = "\033[90m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RED_BOLD = "\033[1;91m"
    CYAN = "\033[96m"


LEVEL_COLORS = {
    logging.DEBUG: Colors.GRAY,
    logging.INFO: Colors.GREEN,
    logging.WARNING: Colors.YELLOW,
    logging.ERROR: Colors.RED,
    logging.CRITICAL: Colors.RED_BOLD,
}


# ============================================================================
# Custom Formatters
# ============================================================================

class StandardFormatter(logging.Formatter):
    """Standard log formatter with task context."""
    
    def __init__(self, include_task: bool = True):
        self.include_task = include_task
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        # Get timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]  # Trim to milliseconds
        
        # Get task context
        task_id = current_task_id.get() or "-"
        
        # Build log line
        level = f"{record.levelname:<8}"
        logger_name = record.name
        
        if self.include_task:
            return f"[{timestamp}] [{level}] [{logger_name}] [{task_id}] - {record.getMessage()}"
        else:
            return f"[{timestamp}] [{level}] [{logger_name}] - {record.getMessage()}"


class ColorFormatter(StandardFormatter):
    """Colored formatter for console output."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Get base formatted message
        message = super().format(record)
        
        # Apply color
        color = LEVEL_COLORS.get(record.levelno, Colors.RESET)
        return f"{color}{message}{Colors.RESET}"


# ============================================================================
# Task File Handler
# ============================================================================

class TaskFileHandler(logging.Handler):
    """
    Handler that routes logs to task-specific files.
    
    Writes logs to {video_path}/task.log when video_path context is set.
    """
    
    def __init__(self):
        super().__init__()
        self._handlers: Dict[str, logging.FileHandler] = {}
        self.setFormatter(StandardFormatter(include_task=True))
    
    def emit(self, record: logging.LogRecord) -> None:
        """Write log record to task-specific file."""
        video_path = current_video_path.get()
        if not video_path:
            return
        
        try:
            handler = self._get_or_create_handler(video_path)
            handler.emit(record)
        except Exception:
            self.handleError(record)
    
    def _get_or_create_handler(self, video_path: str) -> logging.FileHandler:
        """Get or create file handler for video path."""
        if video_path not in self._handlers:
            log_file = Path(video_path) / "task.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            handler = logging.FileHandler(log_file, encoding="utf-8")
            handler.setFormatter(self.formatter)
            self._handlers[video_path] = handler
        
        return self._handlers[video_path]
    
    def close(self) -> None:
        """Close all file handlers."""
        for handler in self._handlers.values():
            handler.close()
        self._handlers.clear()
        super().close()


# ============================================================================
# Task Context Manager
# ============================================================================

class TaskContext:
    """
    Context manager for task logging.
    
    Sets task context variables so all logs within the context
    automatically include task information and route to task.log.
    
    Usage:
        with TaskContext(task_id="abc123", video_id="xyz", video_path="/path/to/video"):
            logger.info("This log includes task context")
    """
    
    def __init__(
        self,
        task_id: Optional[str] = None,
        video_id: Optional[str] = None,
        video_path: Optional[str] = None,
    ):
        self.task_id = task_id
        self.video_id = video_id
        self.video_path = video_path
        self._tokens = []
    
    def __enter__(self) -> "TaskContext":
        if self.task_id:
            self._tokens.append(current_task_id.set(self.task_id))
        if self.video_id:
            self._tokens.append(current_video_id.set(self.video_id))
        if self.video_path:
            self._tokens.append(current_video_path.set(self.video_path))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        for token in self._tokens:
            try:
                token.var.reset(token)
            except ValueError:
                pass
        self._tokens.clear()


# ============================================================================
# Log Manager
# ============================================================================

class LogManager:
    """
    Centralized log manager for SRT Flow.
    
    Manages logging configuration, handlers, and provides
    logger instances to other modules.
    """
    
    _instance: Optional["LogManager"] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        log_dir: str = "data/logs",
        log_level: str = "INFO",
        enable_console: bool = True,
        enable_color: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        if self._initialized:
            return
        
        self._log_dir = Path(log_dir)
        self._log_level = getattr(logging, log_level.upper(), logging.INFO)
        self._enable_console = enable_console
        self._enable_color = enable_color
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        
        self._loggers: Dict[str, logging.Logger] = {}
        self._task_handler: Optional[TaskFileHandler] = None
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize logging system."""
        if self._initialized:
            return
        
        # Create log directory
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self._log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        if self._enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self._log_level)
            if self._enable_color and sys.stdout.isatty():
                console_handler.setFormatter(ColorFormatter())
            else:
                console_handler.setFormatter(StandardFormatter())
            root_logger.addHandler(console_handler)
        
        # Main log file handler (with rotation)
        app_log = self._log_dir / "app.log"
        file_handler = RotatingFileHandler(
            app_log,
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(self._log_level)
        file_handler.setFormatter(StandardFormatter())
        root_logger.addHandler(file_handler)
        
        # Error log file handler
        error_log = self._log_dir / "error.log"
        error_handler = RotatingFileHandler(
            error_log,
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StandardFormatter())
        root_logger.addHandler(error_handler)
        
        # Task file handler
        self._task_handler = TaskFileHandler()
        self._task_handler.setLevel(self._log_level)
        root_logger.addHandler(self._task_handler)
        
        self._initialized = True
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger instance."""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]
    
    def set_level(self, level: str) -> None:
        """Dynamically change log level."""
        new_level = getattr(logging, level.upper(), logging.INFO)
        self._log_level = new_level
        
        root_logger = logging.getLogger()
        root_logger.setLevel(new_level)
        
        for handler in root_logger.handlers:
            if not isinstance(handler, RotatingFileHandler) or \
               handler.level != logging.ERROR:
                handler.setLevel(new_level)
    
    def shutdown(self) -> None:
        """Shutdown logging system."""
        if self._task_handler:
            self._task_handler.close()
        logging.shutdown()
        self._initialized = False


# ============================================================================
# Global Instance and Helpers
# ============================================================================

_log_manager: Optional[LogManager] = None


def init_logger(
    log_dir: str = "data/logs",
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_color: bool = True,
) -> LogManager:
    """Initialize the global log manager."""
    global _log_manager
    _log_manager = LogManager(
        log_dir=log_dir,
        log_level=log_level,
        enable_console=enable_console,
        enable_color=enable_color,
    )
    _log_manager.initialize()
    return _log_manager


def get_log_manager() -> LogManager:
    """Get the global log manager instance."""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
        _log_manager.initialize()
    return _log_manager


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance by name."""
    return get_log_manager().get_logger(name)


def set_log_level(level: str) -> None:
    """Set global log level."""
    get_log_manager().set_level(level)
