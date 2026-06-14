"""
Reference Audio API endpoints.

Provides REST API for managing TTS reference audio files.
"""
import os
import uuid
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas import success_response
from backend.app.deps import get_db
from backend.core import get_logger, get_system_settings
from backend.core.models import ReferenceAudio


router = APIRouter(prefix="/reference-audio", tags=["Reference Audio"])
logger = get_logger("api.reference_audio")

# Allowed audio extensions
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# ============================================================================
# Request/Response Schemas
# ============================================================================

class ReferenceAudioResponse(BaseModel):
    """Reference audio response model."""
    id: str
    name: str
    filename: str
    original_filename: str
    description: Optional[str] = None
    emotion: Optional[str] = None
    content: Optional[str] = None
    file_size: int
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    created_at: str
    updated_at: str


class ReferenceAudioUpdateRequest(BaseModel):
    """Request body for updating reference audio."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    emotion: Optional[str] = Field(None, max_length=50)
    content: Optional[str] = Field(None, max_length=2000)


# ============================================================================
# Helper Functions
# ============================================================================

def get_audio_dir() -> Path:
    """Get reference audio storage directory."""
    settings = get_system_settings()
    audio_dir = Path(settings.data_dir) / "reference_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir


def get_audio_info(file_path: Path) -> dict:
    """Get audio file info using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {}
        
        import json
        data = json.loads(result.stdout)
        
        duration = None
        sample_rate = None
        
        # Get duration from format
        if "format" in data and "duration" in data["format"]:
            duration = float(data["format"]["duration"])
        
        # Get sample rate from audio stream
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                if "sample_rate" in stream:
                    sample_rate = int(stream["sample_rate"])
                if duration is None and "duration" in stream:
                    duration = float(stream["duration"])
                break
        
        return {"duration": duration, "sample_rate": sample_rate}
    except Exception as e:
        logger.warning(f"Failed to get audio info: {e}")
        return {}


def model_to_response(audio: ReferenceAudio) -> dict:
    """Convert model to response dict."""
    return {
        "id": audio.id,
        "name": audio.name,
        "filename": audio.filename,
        "original_filename": audio.original_filename,
        "description": audio.description,
        "emotion": audio.emotion,
        "content": audio.content,
        "file_size": audio.file_size,
        "duration": audio.duration,
        "sample_rate": audio.sample_rate,
        "created_at": audio.created_at.isoformat(),
        "updated_at": audio.updated_at.isoformat(),
    }


# ============================================================================
# Endpoints
# ============================================================================

@router.get("")
async def list_reference_audios(db: AsyncSession = Depends(get_db)):
    """
    List all reference audio files.
    
    Returns list of reference audio metadata.
    """
    result = await db.execute(
        select(ReferenceAudio).order_by(ReferenceAudio.created_at.desc())
    )
    audios = result.scalars().all()
    
    return success_response(
        data=[model_to_response(a) for a in audios]
    )


@router.post("")
async def upload_reference_audio(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    emotion: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a new reference audio file.
    
    Accepts audio files (wav, mp3, m4a, flac, ogg, aac).
    Max file size: 50MB.
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )
    
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    file_content = await file.read()
    
    # Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
    
    # Generate unique filename
    audio_id = str(uuid.uuid4())
    filename = f"{audio_id}{ext}"
    
    # Save file
    audio_dir = get_audio_dir()
    file_path = audio_dir / filename
    
    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Get audio info
        audio_info = get_audio_info(file_path)
        
        # Create database record
        audio = ReferenceAudio(
            id=audio_id,
            name=name,
            filename=filename,
            original_filename=file.filename,
            description=description,
            emotion=emotion,
            content=content,
            file_path=str(file_path),
            file_size=len(file_content),
            duration=audio_info.get("duration"),
            sample_rate=audio_info.get("sample_rate"),
        )
        
        db.add(audio)
        await db.commit()
        await db.refresh(audio)
        
        logger.info(f"Uploaded reference audio: {file.filename} -> {filename}")
        
        return success_response(
            data=model_to_response(audio),
            message="上传成功"
        )
        
    except Exception as e:
        # Clean up file on error
        if file_path.exists():
            file_path.unlink()
        logger.error(f"Failed to upload reference audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/{audio_id}")
async def get_reference_audio(
    audio_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get reference audio metadata by ID."""
    result = await db.execute(
        select(ReferenceAudio).where(ReferenceAudio.id == audio_id)
    )
    audio = result.scalar_one_or_none()
    
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference audio not found"
        )
    
    return success_response(data=model_to_response(audio))


@router.put("/{audio_id}")
async def update_reference_audio(
    audio_id: str,
    request: ReferenceAudioUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update reference audio metadata."""
    result = await db.execute(
        select(ReferenceAudio).where(ReferenceAudio.id == audio_id)
    )
    audio = result.scalar_one_or_none()
    
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference audio not found"
        )
    
    if request.name is not None:
        audio.name = request.name
    if request.description is not None:
        audio.description = request.description
    if request.emotion is not None:
        audio.emotion = request.emotion
    if request.content is not None:
        audio.content = request.content
    
    await db.commit()
    await db.refresh(audio)
    
    logger.info(f"Updated reference audio: {audio_id}")
    
    return success_response(
        data=model_to_response(audio),
        message="更新成功"
    )


@router.delete("/{audio_id}")
async def delete_reference_audio(
    audio_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete reference audio file and metadata."""
    result = await db.execute(
        select(ReferenceAudio).where(ReferenceAudio.id == audio_id)
    )
    audio = result.scalar_one_or_none()
    
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference audio not found"
        )
    
    # Delete file
    file_path = Path(audio.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}")
    
    # Delete database record
    await db.execute(
        delete(ReferenceAudio).where(ReferenceAudio.id == audio_id)
    )
    await db.commit()
    
    logger.info(f"Deleted reference audio: {audio_id}")
    
    return success_response(message="删除成功")


@router.get("/{audio_id}/stream")
async def stream_reference_audio(
    audio_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Stream reference audio file for playback.
    
    Returns the audio file for browser playback.
    """
    result = await db.execute(
        select(ReferenceAudio).where(ReferenceAudio.id == audio_id)
    )
    audio = result.scalar_one_or_none()
    
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference audio not found"
        )
    
    file_path = Path(audio.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found on disk"
        )
    
    # Determine media type
    ext = file_path.suffix.lower()
    media_types = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".aac": "audio/aac",
    }
    media_type = media_types.get(ext, "audio/mpeg")
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=audio.original_filename
    )
