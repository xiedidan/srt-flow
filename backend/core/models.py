"""
SQLAlchemy ORM models for SRT Flow.

Defines all database tables and their relationships.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ============================================================================
# Enums
# ============================================================================

class VideoSource(str, Enum):
    """Video source platforms."""
    YOUTUBE = "youtube"
    BILIBILI = "bilibili"
    LOCAL = "local"


class TaskType(str, Enum):
    """Task types for the processing pipeline."""
    DOWNLOAD = "download"
    ASR = "asr"
    TRANSLATE = "translate"
    TTS = "tts"
    SYNTHESIZE = "synthesize"
    ASSET_GEN = "asset_gen"
    EDITOR = "editor"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class FileType(str, Enum):
    """Video file types."""
    VIDEO_ORIGINAL = "video_original"
    AUDIO_ORIGINAL = "audio_original"
    SUBTITLE_ORIGINAL = "subtitle_original"
    SUBTITLE_TRANSLATED = "subtitle_translated"
    AUDIO_TTS = "audio_tts"
    VIDEO_OUTPUT = "video_output"
    THUMBNAIL = "thumbnail"
    SUMMARY = "summary"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ============================================================================
# Helper Functions
# ============================================================================

def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


# ============================================================================
# Models
# ============================================================================

class Group(Base):
    """Video group model."""
    __tablename__ = "groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="group")


class Tag(Base):
    """Video tag model."""
    __tablename__ = "tags"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#3B82F6", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    videos: Mapped[List["Video"]] = relationship(
        "Video", secondary="video_tags", back_populates="tags"
    )


class VideoTag(Base):
    """Video-Tag association table."""
    __tablename__ = "video_tags"
    
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Video(Base):
    """Video metadata model."""
    __tablename__ = "videos"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[VideoSource] = mapped_column(
        SQLEnum(VideoSource), nullable=False, index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    channel_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    directory_path: Mapped[str] = mapped_column(String(500), nullable=False)
    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    group: Mapped[Optional["Group"]] = relationship("Group", back_populates="videos")
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary="video_tags", back_populates="videos"
    )
    files: Mapped[List["VideoFile"]] = relationship(
        "VideoFile", back_populates="video", cascade="all, delete-orphan"
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task", back_populates="video", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_video_source_external"),
        Index("ix_video_group", "group_id"),
    )



class VideoFile(Base):
    """Video file record model."""
    __tablename__ = "video_files"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    file_type: Mapped[FileType] = mapped_column(SQLEnum(FileType), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="files")
    
    __table_args__ = (
        UniqueConstraint("video_id", "file_type", name="uq_video_file_type"),
    )


class Task(Base):
    """Task queue model."""
    __tablename__ = "tasks"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    video_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[TaskType] = mapped_column(SQLEnum(TaskType), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(
        SQLEnum(TaskPriority), default=TaskPriority.NORMAL, nullable=False
    )
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    video: Mapped[Optional["Video"]] = relationship("Video", back_populates="tasks")
    logs: Mapped[List["TaskLog"]] = relationship(
        "TaskLog", back_populates="task", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("ix_task_priority_created", "priority", "created_at"),
        Index("ix_task_video", "video_id"),
    )


class TaskLog(Base):
    """Task execution log model."""
    __tablename__ = "task_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[LogLevel] = mapped_column(SQLEnum(LogLevel), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    
    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="logs")


class Config(Base):
    """Configuration storage model."""
    __tablename__ = "config"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    __table_args__ = (
        UniqueConstraint("category", "key", name="uq_config_category_key"),
        Index("ix_config_category", "category"),
    )


class AIProviderType(str, Enum):
    """AI provider API types."""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENAI_COMPATIBLE = "openai_compatible"


class ReferenceAudio(Base):
    """Reference audio for TTS voice cloning."""
    __tablename__ = "reference_audios"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Required name
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emotion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Optional emotion tag
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Optional transcript content
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[Optional[float]] = mapped_column(nullable=True)  # seconds
    sample_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class AIProvider(Base):
    """AI Provider configuration model."""
    __tablename__ = "ai_providers"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_type: Mapped[AIProviderType] = mapped_column(
        SQLEnum(AIProviderType), nullable=False
    )
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    __table_args__ = (
        Index("ix_ai_provider_type", "api_type"),
    )
