"""
Repository pattern implementation for data access.

Provides abstraction layer between business logic and database operations.
"""
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.models import (
    Base,
    Video,
    VideoFile,
    Task,
    TaskLog,
    Tag,
    Group,
    Config,
    AIProvider,
    AIProviderType,
    VideoSource,
    TaskType,
    TaskStatus,
    TaskPriority,
    FileType,
    LogLevel,
    ReferenceAudio,
)
from backend.core.exceptions import EntityNotFoundError, DuplicateEntityError


# Type variable for generic repository
ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Base repository with common CRUD operations.
    
    Provides generic data access methods that can be inherited
    by entity-specific repositories.
    """
    
    def __init__(self, session: AsyncSession, model: Type[ModelT]):
        """
        Initialize repository.
        
        Args:
            session: Database session
            model: SQLAlchemy model class
        """
        self._session = session
        self._model = model
    
    async def get_by_id(self, id: Any) -> Optional[ModelT]:
        """Get entity by primary key."""
        return await self._session.get(self._model, id)
    
    async def get_by_id_or_raise(self, id: Any) -> ModelT:
        """Get entity by primary key or raise exception."""
        entity = await self.get_by_id(id)
        if not entity:
            raise EntityNotFoundError(self._model.__name__, str(id))
        return entity
    
    async def get_all(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[ModelT]:
        """Get all entities with pagination."""
        stmt = select(self._model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def create(self, entity: ModelT) -> ModelT:
        """Create a new entity."""
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity
    
    async def update(self, entity: ModelT) -> ModelT:
        """Update an existing entity."""
        await self._session.flush()
        await self._session.refresh(entity)
        return entity
    
    async def delete(self, entity: ModelT) -> None:
        """Delete an entity."""
        await self._session.delete(entity)
        await self._session.flush()
    
    async def delete_by_id(self, id: Any) -> bool:
        """Delete entity by ID. Returns True if deleted."""
        entity = await self.get_by_id(id)
        if entity:
            await self.delete(entity)
            return True
        return False
    
    async def count(self) -> int:
        """Get total count of entities."""
        stmt = select(func.count()).select_from(self._model)
        result = await self._session.execute(stmt)
        return result.scalar() or 0


class VideoRepository(BaseRepository[Video]):
    """Repository for Video entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Video)
    
    async def update(self, video_id: str, updates: Dict[str, Any]) -> Video:
        """
        Update video with given data.
        
        Handles special cases like tags (many-to-many relationship).
        
        Args:
            video_id: Video ID to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated video entity
        """
        from sqlalchemy import update as sql_update
        from backend.core.models import Video
        
        # Handle directory_path separately using raw SQL
        directory_path = updates.pop("directory_path", None)
        
        if directory_path is not None:
            stmt = sql_update(Video).where(Video.id == video_id).values(directory_path=directory_path)
            await self._session.execute(stmt)
        
        if not updates:
            # Only directory was updated, fetch and return
            video = await self.get_by_id(video_id)
            return video
        
        video = await self.get_with_relations(video_id)
        if not video:
            raise EntityNotFoundError("Video", video_id)
        
        # Handle tags separately (many-to-many relationship)
        if "tags" in updates:
            tag_names = updates.pop("tags")
            # Get or create tags
            tag_repo = TagRepository(self._session)
            new_tags = []
            for tag_name in tag_names:
                tag = await tag_repo.get_or_create(tag_name)
                new_tags.append(tag)
            # Replace video tags
            video.tags = new_tags
        
        # Update other fields
        for key, value in updates.items():
            if hasattr(video, key):
                setattr(video, key, value)
        
        await self._session.flush()
        await self._session.refresh(video)
        return video
    
    async def get_by_external_id(
        self, 
        source: VideoSource, 
        external_id: str
    ) -> Optional[Video]:
        """Get video by source and external ID (for deduplication)."""
        stmt = select(Video).where(
            Video.source == source,
            Video.external_id == external_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def exists_by_external_id(
        self, 
        source: VideoSource, 
        external_id: str
    ) -> bool:
        """Check if video exists by external ID."""
        video = await self.get_by_external_id(source, external_id)
        return video is not None
    
    async def get_with_files(self, video_id: str) -> Optional[Video]:
        """Get video with all associated files loaded."""
        stmt = select(Video).options(
            selectinload(Video.files)
        ).where(Video.id == video_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_with_relations(self, video_id: str) -> Optional[Video]:
        """Get video with all relations loaded."""
        stmt = select(Video).options(
            selectinload(Video.files),
            selectinload(Video.tags),
            selectinload(Video.group),
        ).where(Video.id == video_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def search(
        self,
        keyword: Optional[str] = None,
        source: Optional[VideoSource] = None,
        tag_ids: Optional[List[int]] = None,
        group_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Video]:
        """Search videos with filters."""
        stmt = select(Video)
        
        if keyword:
            stmt = stmt.where(Video.title.ilike(f"%{keyword}%"))
        if source:
            stmt = stmt.where(Video.source == source)
        if group_id:
            stmt = stmt.where(Video.group_id == group_id)
        if tag_ids:
            # Videos that have any of the specified tags
            from backend.core.models import VideoTag
            stmt = stmt.join(VideoTag).where(VideoTag.tag_id.in_(tag_ids))
        
        stmt = stmt.order_by(Video.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def count_by_source(self) -> Dict[str, int]:
        """Count videos grouped by source."""
        stmt = select(
            Video.source, func.count(Video.id)
        ).group_by(Video.source)
        result = await self._session.execute(stmt)
        return {row[0].value: row[1] for row in result.all()}
    
    async def list_with_pagination(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort: str = "created_at_desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Video], int]:
        """
        List videos with pagination and filters.
        
        Args:
            filters: Optional filters (keyword, source, tag_ids, group_id)
            sort: Sort order (created_at_desc, created_at_asc, title_asc, title_desc)
            page: Page number (1-indexed)
            page_size: Items per page
            
        Returns:
            Tuple of (videos list, total count)
        """
        filters = filters or {}
        
        # Build base query with eager loading for tags
        stmt = select(Video).options(selectinload(Video.tags))
        count_stmt = select(func.count(Video.id))
        
        # Apply filters
        keyword = filters.get('keyword')
        source = filters.get('source')
        tag_ids = filters.get('tag_ids')
        group_id = filters.get('group_id')
        
        if keyword:
            filter_cond = Video.title.ilike(f"%{keyword}%")
            stmt = stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)
        
        if source:
            filter_cond = Video.source == source
            stmt = stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)
        
        if group_id:
            filter_cond = Video.group_id == group_id
            stmt = stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)
        
        if tag_ids:
            from backend.core.models import VideoTag
            stmt = stmt.join(VideoTag).where(VideoTag.tag_id.in_(tag_ids))
            count_stmt = count_stmt.join(VideoTag).where(VideoTag.tag_id.in_(tag_ids))
        
        # Get total count
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()
        
        # Apply sorting
        sort_map = {
            "created_at_desc": Video.created_at.desc(),
            "created_at_asc": Video.created_at.asc(),
            "title_asc": Video.title.asc(),
            "title_desc": Video.title.desc(),
            "updated_at_desc": Video.updated_at.desc(),
            "updated_at_asc": Video.updated_at.asc(),
        }
        order_by = sort_map.get(sort, Video.created_at.desc())
        stmt = stmt.order_by(order_by)
        
        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        
        # Execute query
        result = await self._session.execute(stmt)
        videos = list(result.scalars().all())
        
        return videos, total


class TaskRepository(BaseRepository[Task]):
    """Repository for Task entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Task)
    
    async def get_pending_tasks(
        self, 
        task_type: Optional[TaskType] = None,
        limit: int = 10
    ) -> List[Task]:
        """Get pending tasks ordered by priority and creation time."""
        stmt = select(Task).where(Task.status == TaskStatus.PENDING)
        
        if task_type:
            stmt = stmt.where(Task.type == task_type)
        
        # Order: high priority first, then by creation time
        stmt = stmt.order_by(
            Task.priority.asc(),  # HIGH < NORMAL < LOW in enum order
            Task.created_at.asc()
        ).limit(limit)
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_running_tasks(
        self, 
        task_type: Optional[TaskType] = None
    ) -> List[Task]:
        """Get currently running tasks."""
        stmt = select(Task).where(Task.status == TaskStatus.RUNNING)
        
        if task_type:
            stmt = stmt.where(Task.type == task_type)
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_video_id(self, video_id: str) -> List[Task]:
        """Get all tasks for a video."""
        stmt = select(Task).where(
            Task.video_id == video_id
        ).order_by(Task.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[int] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """Update task status and related fields."""
        task = await self.get_by_id_or_raise(task_id)
        task.status = status
        
        if progress is not None:
            task.progress = progress
        if error is not None:
            task.error = error
        if result is not None:
            task.result = result
        
        # Set timestamps based on status
        now = datetime.utcnow()
        if status == TaskStatus.RUNNING and not task.started_at:
            task.started_at = now
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = now
        
        return await self.update(task)
    
    async def count_by_status(self) -> Dict[str, int]:
        """Count tasks grouped by status."""
        stmt = select(
            Task.status, func.count(Task.id)
        ).group_by(Task.status)
        result = await self._session.execute(stmt)
        return {row[0].value: row[1] for row in result.all()}
    
    async def count_running_by_type(self) -> Dict[str, int]:
        """Count running tasks grouped by type."""
        stmt = select(
            Task.type, func.count(Task.id)
        ).where(
            Task.status == TaskStatus.RUNNING
        ).group_by(Task.type)
        result = await self._session.execute(stmt)
        return {row[0].value: row[1] for row in result.all()}
    
    async def list_with_pagination(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Task], int]:
        """
        List tasks with pagination and filters.
        
        Args:
            filters: Optional filters (status, task_type, video_id, tag)
            page: Page number (1-indexed)
            page_size: Items per page
            
        Returns:
            Tuple of (tasks list, total count)
        """
        # Build base query with eager loading for video and its tags
        stmt = select(Task).options(
            selectinload(Task.video).selectinload(Video.tags)
        )
        count_stmt = select(func.count(Task.id))
        
        # Check if we need to join with video/tags for filtering
        need_video_join = False
        tag_filter = None
        
        # Apply filters
        if filters:
            if "status" in filters:
                stmt = stmt.where(Task.status == filters["status"])
                count_stmt = count_stmt.where(Task.status == filters["status"])
            if "task_type" in filters:
                from backend.core.models import TaskType
                task_type_map = {
                    'download': TaskType.DOWNLOAD,
                    'asr': TaskType.ASR,
                    'translate': TaskType.TRANSLATE,
                    'tts': TaskType.TTS,
                    'synthesize': TaskType.SYNTHESIZE,
                    'asset_gen': TaskType.ASSET_GEN,
                    'editor': TaskType.EDITOR,
                }
                task_type_enum = task_type_map.get(filters["task_type"])
                if task_type_enum:
                    stmt = stmt.where(Task.type == task_type_enum)
                    count_stmt = count_stmt.where(Task.type == task_type_enum)
            if "video_id" in filters:
                stmt = stmt.where(Task.video_id == filters["video_id"])
                count_stmt = count_stmt.where(Task.video_id == filters["video_id"])
            if "tag" in filters:
                tag_filter = filters["tag"]
                need_video_join = True
        
        # Apply tag filter by joining video -> video_tags -> tags
        if need_video_join and tag_filter:
            from backend.core.models import VideoTag, Tag
            stmt = stmt.join(Video, Task.video_id == Video.id)
            stmt = stmt.join(VideoTag, Video.id == VideoTag.video_id)
            stmt = stmt.join(Tag, VideoTag.tag_id == Tag.id)
            stmt = stmt.where(Tag.name == tag_filter)
            
            count_stmt = count_stmt.join(Video, Task.video_id == Video.id)
            count_stmt = count_stmt.join(VideoTag, Video.id == VideoTag.video_id)
            count_stmt = count_stmt.join(Tag, VideoTag.tag_id == Tag.id)
            count_stmt = count_stmt.where(Tag.name == tag_filter)
        
        # Get total count
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0
        
        # Apply ordering and pagination
        stmt = stmt.order_by(Task.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # Execute query
        result = await self._session.execute(stmt)
        tasks = list(result.scalars().all())
        
        return tasks, total



class VideoFileRepository(BaseRepository[VideoFile]):
    """Repository for VideoFile entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, VideoFile)
    
    async def get_by_video_and_type(
        self, 
        video_id: str, 
        file_type: FileType
    ) -> Optional[VideoFile]:
        """Get file by video ID and file type."""
        stmt = select(VideoFile).where(
            VideoFile.video_id == video_id,
            VideoFile.file_type == file_type
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_video_id(self, video_id: str) -> List[VideoFile]:
        """Get all files for a video."""
        stmt = select(VideoFile).where(VideoFile.video_id == video_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def upsert(
        self,
        video_id: str,
        file_type: FileType,
        file_path: str,
        file_size: Optional[int] = None,
        checksum: Optional[str] = None,
    ) -> VideoFile:
        """Create or update a video file record."""
        existing = await self.get_by_video_and_type(video_id, file_type)
        
        if existing:
            existing.file_path = file_path
            existing.file_size = file_size
            existing.checksum = checksum
            return await self.update(existing)
        else:
            file = VideoFile(
                video_id=video_id,
                file_type=file_type,
                file_path=file_path,
                file_size=file_size,
                checksum=checksum,
            )
            return await self.create(file)


class TagRepository(BaseRepository[Tag]):
    """Repository for Tag entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Tag)
    
    async def get_by_name(self, name: str) -> Optional[Tag]:
        """Get tag by name."""
        stmt = select(Tag).where(Tag.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_or_create(self, name: str, color: str = "#3B82F6") -> Tag:
        """Get existing tag or create new one."""
        tag = await self.get_by_name(name)
        if tag:
            return tag
        return await self.create(Tag(name=name, color=color))
    
    async def get_all_with_count(self) -> List[Dict[str, Any]]:
        """Get all tags with video count."""
        from backend.core.models import VideoTag
        stmt = select(
            Tag,
            func.count(VideoTag.video_id).label("video_count")
        ).outerjoin(VideoTag).group_by(Tag.id)
        result = await self._session.execute(stmt)
        return [
            {"tag": row[0], "video_count": row[1]}
            for row in result.all()
        ]


class GroupRepository(BaseRepository[Group]):
    """Repository for Group entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Group)
    
    async def get_by_name(self, name: str) -> Optional[Group]:
        """Get group by name."""
        stmt = select(Group).where(Group.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_with_count(self) -> List[Dict[str, Any]]:
        """Get all groups with video count."""
        stmt = select(
            Group,
            func.count(Video.id).label("video_count")
        ).outerjoin(Video).group_by(Group.id)
        result = await self._session.execute(stmt)
        return [
            {"group": row[0], "video_count": row[1]}
            for row in result.all()
        ]


class ConfigRepository(BaseRepository[Config]):
    """Repository for Config entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Config)
    
    async def get_by_category(self, category: str) -> List[Config]:
        """Get all config entries for a category."""
        stmt = select(Config).where(Config.category == category)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_key(self, category: str, key: str) -> Optional[Config]:
        """Get config by category and key."""
        stmt = select(Config).where(
            Config.category == category,
            Config.key == key
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def set_value(
        self,
        category: str,
        key: str,
        value: str,
        is_encrypted: bool = False,
        description: Optional[str] = None,
    ) -> Config:
        """Set config value (create or update)."""
        existing = await self.get_by_key(category, key)
        
        if existing:
            existing.value = value
            existing.is_encrypted = is_encrypted
            if description:
                existing.description = description
            return await self.update(existing)
        else:
            config = Config(
                category=category,
                key=key,
                value=value,
                is_encrypted=is_encrypted,
                description=description,
            )
            return await self.create(config)
    
    async def delete_by_key(self, category: str, key: str) -> bool:
        """Delete config by category and key."""
        config = await self.get_by_key(category, key)
        if config:
            await self.delete(config)
            return True
        return False
    
    async def get_category_dict(self, category: str) -> Dict[str, str]:
        """Get all config values for a category as dict."""
        configs = await self.get_by_category(category)
        return {c.key: c.value for c in configs}


class TaskLogRepository(BaseRepository[TaskLog]):
    """Repository for TaskLog entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, TaskLog)
    
    async def get_by_task_id(
        self, 
        task_id: str,
        limit: int = 100,
        level: Optional[LogLevel] = None,
    ) -> List[TaskLog]:
        """Get logs for a task."""
        stmt = select(TaskLog).where(TaskLog.task_id == task_id)
        
        if level:
            stmt = stmt.where(TaskLog.level == level)
        
        stmt = stmt.order_by(TaskLog.timestamp.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def add_log(
        self,
        task_id: str,
        level: LogLevel,
        message: str,
    ) -> TaskLog:
        """Add a log entry for a task."""
        log = TaskLog(
            task_id=task_id,
            level=level,
            message=message,
        )
        return await self.create(log)


class AIProviderRepository(BaseRepository[AIProvider]):
    """Repository for AIProvider entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, AIProvider)
    
    async def get_all_enabled(self) -> List[AIProvider]:
        """Get all enabled AI providers."""
        stmt = select(AIProvider).where(
            AIProvider.is_enabled == True
        ).order_by(AIProvider.created_at.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_type(
        self, 
        api_type: AIProviderType,
        enabled_only: bool = True
    ) -> List[AIProvider]:
        """Get AI providers by type."""
        stmt = select(AIProvider).where(AIProvider.api_type == api_type)
        if enabled_only:
            stmt = stmt.where(AIProvider.is_enabled == True)
        stmt = stmt.order_by(AIProvider.created_at.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_name(self, name: str) -> Optional[AIProvider]:
        """Get AI provider by name."""
        stmt = select(AIProvider).where(AIProvider.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def name_exists(self, name: str, exclude_id: Optional[str] = None) -> bool:
        """Check if provider name already exists."""
        stmt = select(func.count(AIProvider.id)).where(AIProvider.name == name)
        if exclude_id:
            stmt = stmt.where(AIProvider.id != exclude_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0


class ReferenceAudioRepository(BaseRepository[ReferenceAudio]):
    """Repository for ReferenceAudio entity operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ReferenceAudio)
    
    async def get_all_ordered(self) -> List[ReferenceAudio]:
        """Get all reference audios ordered by creation time (newest first)."""
        stmt = select(ReferenceAudio).order_by(ReferenceAudio.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_filename(self, filename: str) -> Optional[ReferenceAudio]:
        """Get reference audio by filename."""
        stmt = select(ReferenceAudio).where(ReferenceAudio.filename == filename)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
