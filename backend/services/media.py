"""
Media Management Service Module.

Provides video indexing, metadata management, tag system,
group management, and file association functionality.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.models import (
    Video, VideoFile, Tag, Group, VideoTag,
    VideoSource, FileType,
)
from backend.core.logger import get_logger


# ============================================================================
# Constants
# ============================================================================

# File type to filename mapping
FILE_PATTERNS = {
    FileType.VIDEO_ORIGINAL: ["video.mp4", "video.mkv", "video.webm"],
    FileType.AUDIO_ORIGINAL: ["audio_original.m4a", "audio_original.mp3"],
    FileType.SUBTITLE_ORIGINAL: ["subtitle_original.srt"],
    FileType.SUBTITLE_TRANSLATED: ["subtitle_translated.srt"],
    FileType.AUDIO_TTS: ["audio_tts.m4a", "audio_tts.mp3", "audio_tts.wav"],
    FileType.VIDEO_OUTPUT: ["video_output.mp4"],
    FileType.THUMBNAIL: ["thumbnail.jpg", "thumbnail.png", "video.jpg", "video.png"],
    FileType.SUMMARY: ["assets/summary.txt", "summary.txt"],
}

# Auto-tag rules
AUTO_TAG_RULES = {
    "来源:YouTube": lambda v: v.source == VideoSource.YOUTUBE,
    "来源:Bilibili": lambda v: v.source == VideoSource.BILIBILI,
    "时长:长视频": lambda v: v.duration and v.duration > 3600,
    "时长:短视频": lambda v: v.duration and v.duration < 60,
}

# File-based auto-tags
FILE_AUTO_TAGS = {
    FileType.SUBTITLE_TRANSLATED: "状态:已翻译",
    FileType.AUDIO_TTS: "状态:已配音",
    FileType.VIDEO_OUTPUT: "状态:已合成",
}

# Preset tag colors
TAG_COLORS = {
    "blue": "#3B82F6",
    "green": "#22C55E",
    "yellow": "#EAB308",
    "red": "#EF4444",
    "purple": "#A855F7",
    "gray": "#6B7280",
}


# ============================================================================
# Configuration
# ============================================================================

class MediaConfig:
    """Media service configuration."""
    
    def __init__(
        self,
        downloads_path: str = "data/downloads",
        trash_retention_days: int = 30,
        auto_index_interval: int = 3600,
        max_search_results: int = 1000,
    ):
        self.downloads_path = downloads_path
        self.trash_retention_days = trash_retention_days
        self.auto_index_interval = auto_index_interval
        self.max_search_results = max_search_results


# ============================================================================
# Search Filter
# ============================================================================

class VideoFilter:
    """Video search filter."""
    
    def __init__(
        self,
        keyword: Optional[str] = None,
        source: Optional[VideoSource] = None,
        tag_ids: Optional[List[int]] = None,
        group_id: Optional[int] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        has_file_types: Optional[List[FileType]] = None,
        in_trash: bool = False,
    ):
        self.keyword = keyword
        self.source = source
        self.tag_ids = tag_ids
        self.group_id = group_id
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.created_after = created_after
        self.created_before = created_before
        self.has_file_types = has_file_types
        self.in_trash = in_trash



# ============================================================================
# File Scanner
# ============================================================================

class FileScanner:
    """Scans video directories for files."""
    
    def __init__(self, base_path: str):
        self._base_path = Path(base_path)
        self._logger = get_logger("media.scanner")
    
    def scan_directory(self, dir_path: Path) -> Dict[FileType, Path]:
        """
        Scan a video directory for known file types.
        
        Args:
            dir_path: Video directory path
            
        Returns:
            Dict mapping file type to file path
        """
        found_files = {}
        
        for file_type, patterns in FILE_PATTERNS.items():
            for pattern in patterns:
                file_path = dir_path / pattern
                if file_path.exists():
                    found_files[file_type] = file_path
                    break
        
        return found_files
    
    def scan_all_directories(self) -> List[Dict[str, Any]]:
        """
        Scan all video directories.
        
        Returns:
            List of directory info dicts
        """
        directories = []
        
        if not self._base_path.exists():
            return directories
        
        for item in self._base_path.iterdir():
            if not item.is_dir():
                continue
            
            # Check for info.json
            info_path = item / "video.info.json"
            if not info_path.exists():
                continue
            
            # Parse directory name for UUID
            dir_name = item.name
            parts = dir_name.split("_", 1)
            video_id = parts[0] if len(parts) > 0 else None
            
            # Scan files
            files = self.scan_directory(item)
            
            directories.append({
                "path": item,
                "video_id": video_id,
                "info_path": info_path,
                "files": files,
            })
        
        return directories
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get file size and modification time."""
        stat = file_path.stat()
        return {
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime),
        }


# ============================================================================
# Media Service
# ============================================================================

class MediaService:
    """
    Media management service.
    
    Provides video indexing, metadata management, tag system,
    group management, and file operations.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        config: Optional[MediaConfig] = None,
    ):
        """
        Initialize media service.
        
        Args:
            session: Database session
            config: Service configuration
        """
        self._session = session
        self._config = config or MediaConfig()
        self._logger = get_logger("media")
        self._scanner = FileScanner(self._config.downloads_path)
    
    # ========================================================================
    # Video CRUD
    # ========================================================================
    
    async def get_video(self, video_id: str) -> Optional[Video]:
        """Get video by ID with relations loaded."""
        stmt = select(Video).options(
            selectinload(Video.files),
            selectinload(Video.tags),
            selectinload(Video.group),
        ).where(Video.id == video_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_videos(
        self,
        filters: Optional[VideoFilter] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> List[Video]:
        """
        Get videos with filtering and pagination.
        
        Args:
            filters: Search filters
            page: Page number (1-based)
            page_size: Items per page
            sort_by: Sort field
            sort_desc: Sort descending
            
        Returns:
            List of videos
        """
        stmt = select(Video).options(
            selectinload(Video.tags),
            selectinload(Video.group),
        )
        
        # Apply filters
        if filters:
            if filters.keyword:
                stmt = stmt.where(Video.title.ilike(f"%{filters.keyword}%"))
            if filters.source:
                stmt = stmt.where(Video.source == filters.source)
            if filters.group_id is not None:
                stmt = stmt.where(Video.group_id == filters.group_id)
            if filters.min_duration:
                stmt = stmt.where(Video.duration >= filters.min_duration)
            if filters.max_duration:
                stmt = stmt.where(Video.duration <= filters.max_duration)
            if filters.created_after:
                stmt = stmt.where(Video.created_at >= filters.created_after)
            if filters.created_before:
                stmt = stmt.where(Video.created_at <= filters.created_before)
            if filters.tag_ids:
                stmt = stmt.join(VideoTag).where(VideoTag.tag_id.in_(filters.tag_ids))
        
        # Sorting
        sort_column = getattr(Video, sort_by, Video.created_at)
        if sort_desc:
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())
        
        # Pagination
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())
    
    async def count_videos(self, filters: Optional[VideoFilter] = None) -> int:
        """Count videos matching filters."""
        stmt = select(func.count(Video.id))
        
        if filters:
            if filters.keyword:
                stmt = stmt.where(Video.title.ilike(f"%{filters.keyword}%"))
            if filters.source:
                stmt = stmt.where(Video.source == filters.source)
            if filters.group_id is not None:
                stmt = stmt.where(Video.group_id == filters.group_id)
        
        result = await self._session.execute(stmt)
        return result.scalar() or 0
    
    async def update_video(
        self,
        video_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        group_id: Optional[int] = None,
    ) -> Optional[Video]:
        """Update video metadata."""
        video = await self.get_video(video_id)
        if not video:
            return None
        
        if title is not None:
            video.title = title
        if description is not None:
            video.description = description
        if group_id is not None:
            video.group_id = group_id if group_id > 0 else None
        
        await self._session.flush()
        return video
    
    async def delete_video(self, video_id: str, hard: bool = False) -> bool:
        """
        Delete video (soft or hard delete).
        
        Args:
            video_id: Video ID
            hard: If True, permanently delete files and records
            
        Returns:
            True if deleted
        """
        video = await self.get_video(video_id)
        if not video:
            return False
        
        if hard:
            # Delete files
            if video.directory_path:
                dir_path = Path(video.directory_path)
                if dir_path.exists():
                    import shutil
                    shutil.rmtree(dir_path)
            
            # Delete database record
            await self._session.delete(video)
        else:
            # Soft delete - move to trash group
            trash_group = await self._get_or_create_trash_group()
            video.group_id = trash_group.id
        
        await self._session.flush()
        return True
    
    async def restore_video(self, video_id: str) -> bool:
        """Restore video from trash."""
        video = await self.get_video(video_id)
        if not video:
            return False
        
        video.group_id = None
        await self._session.flush()
        return True

    
    # ========================================================================
    # Tag Management
    # ========================================================================
    
    async def get_tags(self) -> List[Tag]:
        """Get all tags with video count."""
        stmt = select(Tag).order_by(Tag.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def create_tag(
        self,
        name: str,
        color: str = "#3B82F6",
    ) -> Tag:
        """Create a new tag."""
        tag = Tag(name=name, color=color)
        self._session.add(tag)
        await self._session.flush()
        await self._session.refresh(tag)
        return tag
    
    async def update_tag(
        self,
        tag_id: int,
        name: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Optional[Tag]:
        """Update tag."""
        tag = await self._session.get(Tag, tag_id)
        if not tag:
            return None
        
        if name is not None:
            tag.name = name
        if color is not None:
            tag.color = color
        
        await self._session.flush()
        return tag
    
    async def delete_tag(self, tag_id: int) -> bool:
        """Delete tag and remove from all videos."""
        tag = await self._session.get(Tag, tag_id)
        if not tag:
            return False
        
        await self._session.delete(tag)
        await self._session.flush()
        return True
    
    async def add_tag_to_video(self, video_id: str, tag_id: int) -> bool:
        """Add tag to video."""
        # Check if already exists
        stmt = select(VideoTag).where(
            VideoTag.video_id == video_id,
            VideoTag.tag_id == tag_id,
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none():
            return True  # Already tagged
        
        video_tag = VideoTag(video_id=video_id, tag_id=tag_id)
        self._session.add(video_tag)
        await self._session.flush()
        return True
    
    async def remove_tag_from_video(self, video_id: str, tag_id: int) -> bool:
        """Remove tag from video."""
        stmt = select(VideoTag).where(
            VideoTag.video_id == video_id,
            VideoTag.tag_id == tag_id,
        )
        result = await self._session.execute(stmt)
        video_tag = result.scalar_one_or_none()
        
        if video_tag:
            await self._session.delete(video_tag)
            await self._session.flush()
            return True
        return False
    
    async def get_or_create_tag(self, name: str, color: str = "#3B82F6") -> Tag:
        """Get existing tag or create new one."""
        stmt = select(Tag).where(Tag.name == name)
        result = await self._session.execute(stmt)
        tag = result.scalar_one_or_none()
        
        if tag:
            return tag
        return await self.create_tag(name, color)
    
    # ========================================================================
    # Group Management
    # ========================================================================
    
    async def get_groups(self) -> List[Group]:
        """Get all groups with video count."""
        stmt = select(Group).order_by(Group.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def create_group(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> Group:
        """Create a new group."""
        group = Group(name=name, description=description)
        self._session.add(group)
        await self._session.flush()
        await self._session.refresh(group)
        return group
    
    async def update_group(
        self,
        group_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Group]:
        """Update group."""
        group = await self._session.get(Group, group_id)
        if not group:
            return None
        
        if name is not None:
            group.name = name
        if description is not None:
            group.description = description
        
        await self._session.flush()
        return group
    
    async def delete_group(self, group_id: int) -> bool:
        """Delete group (videos become ungrouped)."""
        group = await self._session.get(Group, group_id)
        if not group:
            return False
        
        # Don't delete trash group
        if group.name == "__trash__":
            return False
        
        await self._session.delete(group)
        await self._session.flush()
        return True
    
    async def set_video_group(self, video_id: str, group_id: Optional[int]) -> bool:
        """Set video's group."""
        video = await self._session.get(Video, video_id)
        if not video:
            return False
        
        video.group_id = group_id
        await self._session.flush()
        return True
    
    async def _get_or_create_trash_group(self) -> Group:
        """Get or create the trash group."""
        stmt = select(Group).where(Group.name == "__trash__")
        result = await self._session.execute(stmt)
        group = result.scalar_one_or_none()
        
        if group:
            return group
        
        return await self.create_group("__trash__", "Recycle bin")

    
    # ========================================================================
    # File Management
    # ========================================================================
    
    async def get_video_files(self, video_id: str) -> List[VideoFile]:
        """Get all files for a video."""
        stmt = select(VideoFile).where(VideoFile.video_id == video_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_file_content(
        self,
        video_id: str,
        file_type: FileType,
    ) -> Optional[str]:
        """
        Read text file content.
        
        Args:
            video_id: Video ID
            file_type: File type (must be text file)
            
        Returns:
            File content or None
        """
        stmt = select(VideoFile).where(
            VideoFile.video_id == video_id,
            VideoFile.file_type == file_type,
        )
        result = await self._session.execute(stmt)
        video_file = result.scalar_one_or_none()
        
        if not video_file:
            return None
        
        file_path = Path(video_file.file_path)
        if not file_path.exists():
            return None
        
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            self._logger.error(f"Failed to read file {file_path}: {e}")
            return None
    
    async def save_file_content(
        self,
        video_id: str,
        file_type: FileType,
        content: str,
    ) -> bool:
        """
        Save text file content.
        
        Args:
            video_id: Video ID
            file_type: File type
            content: Content to save
            
        Returns:
            True if saved successfully
        """
        stmt = select(VideoFile).where(
            VideoFile.video_id == video_id,
            VideoFile.file_type == file_type,
        )
        result = await self._session.execute(stmt)
        video_file = result.scalar_one_or_none()
        
        if not video_file:
            # Create new file
            video = await self.get_video(video_id)
            if not video or not video.directory_path:
                return False
            
            # Determine filename
            patterns = FILE_PATTERNS.get(file_type, [])
            if not patterns:
                return False
            
            file_path = Path(video.directory_path) / patterns[0]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            video_file = VideoFile(
                video_id=video_id,
                file_type=file_type,
                file_path=str(file_path),
            )
            self._session.add(video_file)
        
        file_path = Path(video_file.file_path)
        
        try:
            file_path.write_text(content, encoding="utf-8")
            video_file.file_size = len(content.encode("utf-8"))
            await self._session.flush()
            return True
        except Exception as e:
            self._logger.error(f"Failed to save file {file_path}: {e}")
            return False
    
    async def associate_file(
        self,
        video_id: str,
        file_type: FileType,
        file_path: str,
    ) -> Optional[VideoFile]:
        """
        Associate an external file with a video.
        
        Args:
            video_id: Video ID
            file_type: File type
            file_path: Path to file
            
        Returns:
            VideoFile record or None
        """
        path = Path(file_path)
        if not path.exists():
            return None
        
        # Check if already exists
        stmt = select(VideoFile).where(
            VideoFile.video_id == video_id,
            VideoFile.file_type == file_type,
        )
        result = await self._session.execute(stmt)
        video_file = result.scalar_one_or_none()
        
        file_info = self._scanner.get_file_info(path)
        
        if video_file:
            video_file.file_path = str(path)
            video_file.file_size = file_info["size"]
        else:
            video_file = VideoFile(
                video_id=video_id,
                file_type=file_type,
                file_path=str(path),
                file_size=file_info["size"],
            )
            self._session.add(video_file)
        
        await self._session.flush()
        return video_file
    
    # ========================================================================
    # Indexing
    # ========================================================================
    
    async def scan_and_index(self) -> Dict[str, int]:
        """
        Scan downloads directory and index all videos.
        
        Returns:
            Stats dict with counts
        """
        stats = {"scanned": 0, "created": 0, "updated": 0, "errors": 0}
        
        directories = self._scanner.scan_all_directories()
        
        for dir_info in directories:
            stats["scanned"] += 1
            
            try:
                video_id = dir_info["video_id"]
                info_path = dir_info["info_path"]
                files = dir_info["files"]
                
                # Check if video exists
                video = await self._session.get(Video, video_id) if video_id else None
                
                if not video:
                    # Create new video from info.json
                    video = await self._create_video_from_info(
                        info_path, dir_info["path"]
                    )
                    if video:
                        stats["created"] += 1
                else:
                    stats["updated"] += 1
                
                if video:
                    # Update file records
                    await self._sync_video_files(video.id, dir_info["path"], files)
                    # Apply auto-tags
                    await self._apply_auto_tags(video)
                    
            except Exception as e:
                self._logger.error(f"Error indexing {dir_info['path']}: {e}")
                stats["errors"] += 1
        
        await self._session.flush()
        return stats
    
    async def _create_video_from_info(
        self,
        info_path: Path,
        dir_path: Path,
    ) -> Optional[Video]:
        """Create video record from info.json."""
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            
            # Determine source
            extractor = info.get("extractor", "").lower()
            if "youtube" in extractor:
                source = VideoSource.YOUTUBE
            elif "bilibili" in extractor:
                source = VideoSource.BILIBILI
            else:
                source = VideoSource.LOCAL
            
            video = Video(
                title=info.get("title", "Unknown"),
                source=source,
                external_id=info.get("id"),
                channel_name=info.get("uploader") or info.get("channel"),
                channel_id=info.get("uploader_id") or info.get("channel_id"),
                duration=info.get("duration"),
                thumbnail_url=info.get("thumbnail"),
                description=info.get("description"),
                directory_path=str(dir_path),
                extra_data={
                    "webpage_url": info.get("webpage_url"),
                    "upload_date": info.get("upload_date"),
                    "view_count": info.get("view_count"),
                },
            )
            
            self._session.add(video)
            await self._session.flush()
            await self._session.refresh(video)
            return video
            
        except Exception as e:
            self._logger.error(f"Failed to create video from {info_path}: {e}")
            return None
    
    async def _sync_video_files(
        self,
        video_id: str,
        dir_path: Path,
        found_files: Dict[FileType, Path],
    ) -> None:
        """Sync video file records with filesystem."""
        for file_type, file_path in found_files.items():
            file_info = self._scanner.get_file_info(file_path)
            
            stmt = select(VideoFile).where(
                VideoFile.video_id == video_id,
                VideoFile.file_type == file_type,
            )
            result = await self._session.execute(stmt)
            video_file = result.scalar_one_or_none()
            
            if video_file:
                video_file.file_path = str(file_path)
                video_file.file_size = file_info["size"]
            else:
                video_file = VideoFile(
                    video_id=video_id,
                    file_type=file_type,
                    file_path=str(file_path),
                    file_size=file_info["size"],
                )
                self._session.add(video_file)
    
    async def _apply_auto_tags(self, video: Video) -> None:
        """Apply automatic tags based on video properties."""
        # Property-based tags
        for tag_name, condition in AUTO_TAG_RULES.items():
            if condition(video):
                tag = await self.get_or_create_tag(tag_name)
                await self.add_tag_to_video(video.id, tag.id)
        
        # File-based tags
        files = await self.get_video_files(video.id)
        file_types = {f.file_type for f in files}
        
        for file_type, tag_name in FILE_AUTO_TAGS.items():
            if file_type in file_types:
                tag = await self.get_or_create_tag(tag_name)
                await self.add_tag_to_video(video.id, tag.id)
    
    # ========================================================================
    # Trash Management
    # ========================================================================
    
    async def clean_trash(self, older_than_days: Optional[int] = None) -> int:
        """
        Permanently delete videos in trash older than specified days.
        
        Args:
            older_than_days: Days threshold (default from config)
            
        Returns:
            Number of deleted videos
        """
        days = older_than_days or self._config.trash_retention_days
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        trash_group = await self._get_or_create_trash_group()
        
        stmt = select(Video).where(
            Video.group_id == trash_group.id,
            Video.updated_at < cutoff,
        )
        result = await self._session.execute(stmt)
        videos = list(result.scalars().all())
        
        deleted = 0
        for video in videos:
            if await self.delete_video(video.id, hard=True):
                deleted += 1
        
        return deleted
