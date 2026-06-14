"""
Video management API endpoints.

Provides REST API for managing videos and their associated files.
"""
from typing import Any, Dict, List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas import success_response
from backend.app.deps import get_db
from backend.core import get_logger, get_system_settings


router = APIRouter(prefix="/videos", tags=["Videos"])
logger = get_logger("api.videos")


# File type mapping
FILE_TYPE_MAP = {
    "video": "video.mp4",
    "audio_original": "audio_original.m4a",
    "audio_tts": "audio_tts.m4a",
    "subtitle_original": "subtitle_original.srt",
    "subtitle_translated": "subtitle_translated.srt",
    "video_output": "video_output.mp4",
    "summary": "assets/summary.txt",
    "title_candidates": "assets/title_candidates.txt",
    "thumbnail": "assets/thumbnail.jpg",
    "log": "task.log",
    "metadata": "video.info.json",
}


# ============================================================================
# Request/Response Schemas
# ============================================================================

class VideoUpdateRequest(BaseModel):
    """Request body for updating video information."""
    title: Optional[str] = Field(None, description="Video title")
    tags: Optional[List[str]] = Field(None, description="Video tags")
    group_id: Optional[str] = Field(None, description="Group ID")
    directory: Optional[str] = Field(None, description="Video directory path")


class FileContentRequest(BaseModel):
    """Request body for saving file content."""
    content: str = Field(..., description="File content")


class VideoResponse(BaseModel):
    """Video response model."""
    id: str
    title: str
    source: Optional[str] = None
    duration: Optional[int] = None
    tags: List[str] = []
    group_id: Optional[str] = None
    directory: Optional[str] = None
    files: Dict[str, Optional[str]] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

def get_video_files(video_dir: Path) -> Dict[str, Optional[str]]:
    """Get available files for a video."""
    files = {}
    for file_type, filename in FILE_TYPE_MAP.items():
        file_path = video_dir / filename
        files[file_type] = str(file_path) if file_path.exists() else None
    return files


def get_video_codec(video_path: Path) -> Optional[str]:
    """
    Get video codec using ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Codec name (e.g., 'h264', 'hevc') or None if detection fails
    """
    import subprocess
    
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            return result.stdout.strip().lower()
        return None
    except Exception as e:
        logger.warning(f"Failed to detect video codec: {e}")
        return None


def is_browser_compatible_codec(codec: Optional[str]) -> bool:
    """
    Check if codec is compatible with browser video playback.
    
    H264/AVC is widely supported, HEVC/H265 is not supported in most browsers.
    """
    if not codec:
        return True  # Assume compatible if unknown
    
    compatible_codecs = ["h264", "avc", "avc1", "vp8", "vp9", "av1"]
    return codec in compatible_codecs


# ============================================================================
# Endpoints
# ============================================================================

@router.get("")
async def list_videos(
    tag: Optional[str] = Query(None, description="Filter by tag"),
    keyword: Optional[str] = Query(None, description="Search keyword"),
    sort: str = Query("created_at_desc", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    include_downloading: bool = Query(True, description="Include downloading videos"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get video list with optional filters.
    
    Supports filtering by tag, keyword search, and sorting.
    When include_downloading is True, also returns pending/running download tasks as "downloading" videos.
    """
    from backend.core.repositories import VideoRepository, TaskRepository
    from backend.core.models import TaskType, TaskStatus
    
    try:
        repo = VideoRepository(db)
        
        # Build filters
        filters = {}
        if tag:
            filters["tag"] = tag
        if keyword:
            filters["keyword"] = keyword
        
        # Get videos with pagination
        videos, total = await repo.list_with_pagination(
            filters=filters,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        
        settings = get_system_settings()
        
        items = []
        
        # Add downloading tasks as pseudo-videos (only on first page without filters)
        if include_downloading and page == 1 and not tag and not keyword:
            task_repo = TaskRepository(db)
            # Get pending and running download tasks
            download_tasks, _ = await task_repo.list_with_pagination(
                filters={"task_type": "download"},
                page=1,
                page_size=50,
            )
            
            for task in download_tasks:
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    # Extract info from payload
                    payload = task.payload or {}
                    url = payload.get("url", "")
                    
                    # Use fetched title if available, otherwise use URL
                    title = payload.get("title")
                    if not title:
                        title = url[:60] + "..." if len(url) > 60 else url
                    
                    # Get thumbnail URL from metadata
                    thumbnail_url = payload.get("thumbnail_url")
                    
                    # Detect source from URL
                    source = "unknown"
                    if "youtube.com" in url or "youtu.be" in url:
                        source = "youtube"
                    elif "bilibili.com" in url or "b23.tv" in url:
                        source = "bilibili"
                    
                    items.append({
                        "id": f"task_{task.id}",  # Prefix to distinguish from real videos
                        "task_id": task.id,
                        "title": title,
                        "thumbnail_url": thumbnail_url,  # Remote thumbnail URL
                        "source": source,
                        "duration": payload.get("duration"),
                        "channel_name": payload.get("channel_name"),
                        "tags": payload.get("tags", []),
                        "group_id": None,
                        "directory": None,
                        "files": {},
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "updated_at": None,
                        "is_downloading": True,
                        "download_status": task.status.value,
                        "download_progress": task.progress or 0,
                    })
        
        for v in videos:
            video_dir = Path(v.directory_path) if v.directory_path else None
            files = get_video_files(video_dir) if video_dir and video_dir.exists() else {}
            
            items.append({
                "id": v.id,
                "title": v.title,
                "source": v.source.value if hasattr(v.source, 'value') else v.source,
                "duration": v.duration,
                "tags": [t.name for t in (v.tags or [])],
                "group_id": v.group_id,
                "directory": v.directory_path,
                "files": files,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "updated_at": v.updated_at.isoformat() if v.updated_at else None,
                "is_downloading": False,
            })
        
        return success_response(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list videos: {str(e)}"
        )


@router.get("/{video_id}")
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get video details by ID.
    
    Returns video metadata, file paths, and associated task history.
    """
    from backend.core.repositories import VideoRepository, TaskRepository
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_with_relations(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        video_dir = Path(video.directory_path) if video.directory_path else None
        files = get_video_files(video_dir) if video_dir and video_dir.exists() else {}
        
        # Detect video codec for browser compatibility check
        video_codec = None
        browser_compatible = True
        if video_dir and video_dir.exists():
            video_file = video_dir / "video.mp4"
            if video_file.exists():
                video_codec = get_video_codec(video_file)
                browser_compatible = is_browser_compatible_codec(video_codec)
        
        # Get associated tasks
        task_repo = TaskRepository(db)
        tasks, _ = await task_repo.list_with_pagination(
            filters={"video_id": video_id},
            page=1,
            page_size=50,
        )
        
        task_history = [
            {
                "id": t.id,
                "type": t.type.value if hasattr(t.type, 'value') else t.type,
                "status": t.status.value,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]
        
        return success_response(
            data={
                "id": video.id,
                "title": video.title,
                "source": video.source.value if hasattr(video.source, 'value') else video.source,
                "external_id": video.external_id,
                "duration": video.duration,
                "tags": [t.name for t in (video.tags or [])],
                "group_id": video.group_id,
                "directory": video.directory_path,
                "files": files,
                "video_codec": video_codec,
                "browser_compatible": browser_compatible,
                "extra_data": video.extra_data,
                "task_history": task_history,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "updated_at": video.updated_at.isoformat() if video.updated_at else None,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video: {str(e)}"
        )


@router.patch("/{video_id}")
async def update_video(
    video_id: str,
    request: VideoUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update video information.
    
    Supports updating title, tags, and group.
    """
    from backend.core.repositories import VideoRepository
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        # Build update dict
        updates = {}
        if request.title is not None:
            updates["title"] = request.title
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.group_id is not None:
            updates["group_id"] = request.group_id
        if request.directory is not None:
            from sqlalchemy import text
            await db.execute(
                text("UPDATE videos SET directory_path = :dir WHERE id = :id"),
                {"dir": request.directory, "id": video_id}
            )
            await db.commit()
            logger.info(f"Video {video_id} directory updated to: {request.directory}")
            # Return success
            return success_response(
                data={
                    "id": video_id,
                    "directory": request.directory,
                },
                message="Directory updated"
            )
        
        if updates:
            video = await repo.update(video_id, updates)
            logger.info(f"Video {video_id} updated: {list(updates.keys())}")
        else:
            # No updates, just get the video with relations
            video = await repo.get_with_relations(video_id)
        
        return success_response(
            data={
                "id": video.id,
                "title": video.title,
                "tags": [t.name for t in (video.tags or [])],
                "group_id": video.group_id,
            },
            message="Video updated"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update video: {str(e)}"
        )


@router.get("/{video_id}/files/{file_type}/content")
async def get_file_content(
    video_id: str,
    file_type: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get text file content.
    
    Supported file types: subtitle_original, subtitle_translated, summary, title_candidates, log
    """
    from backend.core.repositories import VideoRepository
    
    # Validate file type
    text_types = ["subtitle_original", "subtitle_translated", "summary", "title_candidates", "log", "metadata"]
    if file_type not in text_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type for content reading: {file_type}"
        )
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        settings = get_system_settings()
        video_dir = Path(video.directory_path) if video.directory_path else None
        
        if not video_dir or not video_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video directory not found"
            )
        
        filename = FILE_TYPE_MAP.get(file_type)
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown file type: {file_type}"
            )
        
        file_path = video_dir / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_type}"
            )
        
        content = file_path.read_text(encoding="utf-8")
        
        return success_response(
            data={
                "file_type": file_type,
                "content": content,
                "path": str(file_path),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read file content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )


@router.put("/{video_id}/files/{file_type}/content")
async def save_file_content(
    video_id: str,
    file_type: str,
    request: FileContentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Save text file content.
    
    Used for editing subtitles or summaries from the frontend.
    """
    from backend.core.repositories import VideoRepository
    
    # Validate file type (only allow editing certain files)
    editable_types = ["subtitle_original", "subtitle_translated", "summary", "title_candidates"]
    if file_type not in editable_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not editable: {file_type}"
        )
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        settings = get_system_settings()
        video_dir = Path(video.directory_path) if video.directory_path else None
        
        if not video_dir or not video_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video directory not found"
            )
        
        filename = FILE_TYPE_MAP.get(file_type)
        file_path = video_dir / filename
        
        # Ensure parent directory exists (for assets/)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save content
        file_path.write_text(request.content, encoding="utf-8")
        
        logger.info(f"File saved: {file_path}")
        
        return success_response(
            data={
                "file_type": file_type,
                "path": str(file_path),
                "size": len(request.content),
            },
            message="File saved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save file content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )


@router.api_route("/{video_id}/preview", methods=["GET", "HEAD"])
async def preview_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get video preview URL/path.
    
    Returns the path to the video file for streaming.
    Supports Range requests for seeking.
    """
    from backend.core.repositories import VideoRepository
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        settings = get_system_settings()
        video_dir = Path(video.directory_path) if video.directory_path else None
        
        if not video_dir or not video_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video directory not found"
            )
        
        # Check for output video first, then original
        video_path = video_dir / "video_output.mp4"
        if not video_path.exists():
            video_path = video_dir / "video.mp4"
        
        if not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found"
            )
        
        # Use ASCII-safe filename to avoid encoding issues
        from urllib.parse import quote
        safe_filename = quote(f"{video.title}.mp4", safe='')
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=safe_filename,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview video: {str(e)}"
        )


@router.api_route("/{video_id}/stream", methods=["GET", "HEAD"])
async def stream_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream video file with Range request support.
    
    This endpoint is optimized for video playback with seeking support.
    """
    from backend.core.repositories import VideoRepository
    from urllib.parse import quote
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            logger.warning(f"Video not found in database: {video_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        video_dir = Path(video.directory_path) if video.directory_path else None
        logger.debug(f"Video directory path: {video_dir}")
        
        if not video_dir or not video_dir.exists():
            logger.warning(f"Video directory not found: {video_dir}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video directory not found: {video_dir}"
            )
        
        # Check for output video first, then original
        video_path = video_dir / "video_output.mp4"
        if not video_path.exists():
            video_path = video_dir / "video.mp4"
        
        if not video_path.exists():
            logger.warning(f"Video file not found in directory: {video_dir}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found"
            )
        
        logger.debug(f"Streaming video file: {video_path}")
        
        # Use FileResponse which handles Range requests automatically
        # Use ASCII-safe filename to avoid encoding issues in Content-Disposition header
        safe_filename = quote(f"{video.title}.mp4", safe='')
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=safe_filename,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream video {video_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream video: {str(e)}"
        )


def _extract_first_frame(video_path: Path, output_path: Path) -> bool:
    """
    Extract first frame from video using ffmpeg.
    
    Args:
        video_path: Path to video file
        output_path: Path to save thumbnail
        
    Returns:
        True if successful
    """
    import subprocess
    
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use ffmpeg to extract first frame
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            "-y",  # Overwrite output
            str(output_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
        )
        
        return output_path.exists()
    except Exception as e:
        logger.error(f"Failed to extract frame: {e}")
        return False


@router.get("/{video_id}/thumbnail")
async def get_thumbnail(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get video thumbnail image.
    
    Returns the thumbnail image file for the video.
    Searches for thumbnail in multiple locations and formats.
    If no thumbnail exists, automatically extracts first frame from video.
    """
    from backend.core.repositories import VideoRepository
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        video_dir = Path(video.directory_path) if video.directory_path else None
        
        if not video_dir or not video_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video directory not found"
            )
        
        # Search for thumbnail in multiple locations and formats
        # Priority: generated thumbnail > downloaded thumbnail > auto-generated
        thumbnail_candidates = [
            video_dir / "assets" / "thumbnail.jpg",
            video_dir / "assets" / "thumbnail.png",
            video_dir / "thumbnail.jpg",
            video_dir / "thumbnail.png",
            video_dir / "video.jpg",
            video_dir / "video.png",
            video_dir / "video.webp",
        ]
        
        thumbnail_path = None
        for candidate in thumbnail_candidates:
            if candidate.exists():
                thumbnail_path = candidate
                break
        
        # If no thumbnail found, try to extract first frame from video
        if not thumbnail_path:
            video_file = video_dir / "video.mp4"
            if not video_file.exists():
                video_file = video_dir / "video_output.mp4"
            
            if video_file.exists():
                # Generate thumbnail from first frame
                auto_thumbnail = video_dir / "thumbnail_auto.jpg"
                if _extract_first_frame(video_file, auto_thumbnail):
                    thumbnail_path = auto_thumbnail
        
        if not thumbnail_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thumbnail not found and could not be generated"
            )
        
        # Determine media type
        suffix = thumbnail_path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/jpeg")
        
        return FileResponse(
            path=str(thumbnail_path),
            media_type=media_type,
            filename=f"thumbnail{suffix}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thumbnail for video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get thumbnail: {str(e)}"
        )


@router.api_route("/{video_id}/audio/tts", methods=["GET", "HEAD"])
async def stream_tts_audio(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream TTS audio file.
    
    Returns the synthesized TTS audio file for playback.
    """
    from backend.core.repositories import VideoRepository
    from urllib.parse import quote
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        video_dir = Path(video.directory_path) if video.directory_path else None
        
        if not video_dir or not video_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video directory not found"
            )
        
        # Check for TTS audio file
        audio_path = video_dir / "audio_tts.m4a"
        media_type = "audio/mp4"
        
        # Also check for other formats
        if not audio_path.exists():
            audio_path = video_dir / "audio_tts.mp3"
            media_type = "audio/mpeg"
        if not audio_path.exists():
            audio_path = video_dir / "audio_tts.wav"
            media_type = "audio/wav"
        
        if not audio_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TTS audio file not found"
            )
        
        safe_filename = quote(f"{video.title}_tts{audio_path.suffix}", safe='')
        return FileResponse(
            path=str(audio_path),
            media_type=media_type,
            filename=safe_filename,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream TTS audio for video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream TTS audio: {str(e)}"
        )


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    delete_files: bool = Query(False, description="Also delete video files"),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a video record.
    
    Optionally deletes associated files on disk.
    """
    from backend.core.repositories import VideoRepository
    import shutil
    
    try:
        repo = VideoRepository(db)
        video = await repo.get_by_id(video_id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )
        
        # Delete files if requested
        if delete_files and video.directory_path:
            settings = get_system_settings()
            video_dir = Path(settings.downloads_dir) / video.directory
            if video_dir.exists():
                shutil.rmtree(video_dir)
                logger.info(f"Deleted video directory: {video_dir}")
        
        # Delete database record
        await repo.delete(video_id)
        
        logger.info(f"Video {video_id} deleted")
        
        return success_response(
            data={"id": video_id, "files_deleted": delete_files},
            message="Video deleted"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete video: {str(e)}"
        )
