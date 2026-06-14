"""
Core modules for SRT Flow backend.

This package contains fundamental components:
- config: Configuration management
- database: Database connection and session management
- models: SQLAlchemy ORM models
- repositories: Data access layer
- encryption: Sensitive data encryption
- logger: Logging management
- exceptions: Core exception classes
"""
from backend.core.config import (
    ConfigManager,
    get_config_manager,
    init_config_manager,
    get_system_settings,
    SystemSettings,
    GlobalConfig,
    DownloadConfig,
    ASRConfig,
    TranslateConfig,
    TTSConfig,
    SynthesisConfig,
    AssetConfig,
    CONFIG_MODELS,
    SENSITIVE_FIELDS,
)
from backend.core.encryption import (
    EncryptionManager,
    get_encryption_manager,
)
from backend.core.database import (
    DatabaseManager,
    get_database_manager,
    init_database,
    close_database,
    get_db_session,
)
from backend.core.models import (
    Base,
    Video,
    VideoFile,
    Task,
    TaskLog,
    Tag,
    Group,
    Config,
    VideoTag,
    VideoSource,
    TaskType,
    TaskStatus,
    TaskPriority,
    FileType,
    LogLevel,
)
from backend.core.repositories import (
    BaseRepository,
    VideoRepository,
    VideoFileRepository,
    TaskRepository,
    TaskLogRepository,
    TagRepository,
    GroupRepository,
    ConfigRepository,
)
from backend.core.logger import (
    LogManager,
    TaskContext,
    init_logger,
    get_log_manager,
    get_logger,
    set_log_level,
    current_task_id,
    current_video_id,
    current_video_path,
)
from backend.core.exceptions import (
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    ConfigEncryptionError,
    ConfigDecryptionError,
    DatabaseError,
    DatabaseNotInitializedError,
    EntityNotFoundError,
    DuplicateEntityError,
    DatabaseConnectionError,
)


# Re-export mask_sensitive as module-level function
def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive value for display."""
    return EncryptionManager.mask_sensitive(value, visible_chars)


__all__ = [
    # Config Manager
    "ConfigManager",
    "get_config_manager",
    "init_config_manager",
    "get_system_settings",
    # Config Models
    "SystemSettings",
    "GlobalConfig",
    "DownloadConfig",
    "ASRConfig",
    "TranslateConfig",
    "TTSConfig",
    "SynthesisConfig",
    "AssetConfig",
    "CONFIG_MODELS",
    "SENSITIVE_FIELDS",
    # Encryption
    "EncryptionManager",
    "get_encryption_manager",
    "mask_sensitive",
    # Database
    "DatabaseManager",
    "get_database_manager",
    "init_database",
    "close_database",
    "get_db_session",
    # Models
    "Base",
    "Video",
    "VideoFile",
    "Task",
    "TaskLog",
    "Tag",
    "Group",
    "Config",
    "VideoTag",
    "VideoSource",
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    "FileType",
    "LogLevel",
    # Repositories
    "BaseRepository",
    "VideoRepository",
    "VideoFileRepository",
    "TaskRepository",
    "TaskLogRepository",
    "TagRepository",
    "GroupRepository",
    "ConfigRepository",
    # Logger
    "LogManager",
    "TaskContext",
    "init_logger",
    "get_log_manager",
    "get_logger",
    "set_log_level",
    "current_task_id",
    "current_video_id",
    "current_video_path",
    # Exceptions
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "ConfigEncryptionError",
    "ConfigDecryptionError",
    "DatabaseError",
    "DatabaseNotInitializedError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "DatabaseConnectionError",
]
