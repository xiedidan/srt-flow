"""
TTS (Text-to-Speech) API endpoints.

Provides REST API for TTS-related operations including sentence merge preview and voice preview.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import io

from backend.app.schemas import success_response
from backend.app.deps import get_db
from backend.core import get_logger


router = APIRouter(prefix="/tts", tags=["TTS"])
logger = get_logger("api.tts")


# ============================================================================
# Request/Response Schemas
# ============================================================================

class SubtitleEntryResponse(BaseModel):
    """Original subtitle entry."""
    index: int
    start_time: float
    end_time: float
    text: str


class MergedEntryResponse(BaseModel):
    """Merged subtitle entry."""
    merged_text: str
    original_indices: List[int]
    start_time: float
    end_time: float


class SentenceMergePreviewRequest(BaseModel):
    """Request body for sentence merge preview."""
    video_id: str = Field(..., description="Video UUID")
    subtitle_path: Optional[str] = Field(None, description="Optional subtitle path override")


class SentenceMergePreviewResponse(BaseModel):
    """Response for sentence merge preview."""
    original_entries: List[SubtitleEntryResponse]
    merged_entries: List[MergedEntryResponse]
    original_count: int
    merged_count: int


class ManualMergeRequest(BaseModel):
    """Request body for manual merge operation."""
    entries: List[MergedEntryResponse] = Field(..., description="Current merged entries")
    action: str = Field(..., description="Action: merge, split, edit")
    target_index: int = Field(..., description="Index of target entry")
    # For merge action
    merge_with_index: Optional[int] = Field(None, description="Index to merge with (for merge action)")
    # For edit action
    new_text: Optional[str] = Field(None, description="New text (for edit action)")
    # For split action
    split_at_char: Optional[int] = Field(None, description="Character position to split at (for split action)")


class VoicePreviewRequest(BaseModel):
    """Request body for voice preview."""
    engine: str = Field(..., description="TTS engine: azure_tts, edge_tts, volc_tts")
    voice: str = Field(..., description="Voice name/ID")
    text: str = Field(default="你好，这是语音合成的试听效果。", description="Text to synthesize")


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/sentence-merge/preview")
async def preview_sentence_merge(
    request: SentenceMergePreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Preview AI sentence merge results without executing TTS.
    
    This endpoint:
    1. Loads the subtitle file for the video
    2. Calls AI to merge fragmented sentences
    3. Returns both original and merged entries for comparison
    """
    from backend.core.repositories import VideoRepository
    from backend.core import get_config_manager
    from backend.services.tts import TTSSRTParser, SentenceMerger, SentenceMergeError
    
    try:
        # Resolve subtitle path
        subtitle_path = request.subtitle_path
        if not subtitle_path:
            video_repo = VideoRepository(db)
            video = await video_repo.get_by_id(request.video_id)
            if not video or not video.directory_path:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Video not found: {request.video_id}"
                )
            
            video_dir = Path(video.directory_path)
            # Prefer translated subtitle
            subtitle_file = video_dir / "subtitle_translated.srt"
            if not subtitle_file.exists():
                subtitle_file = video_dir / "subtitle_original.srt"
            
            if not subtitle_file.exists():
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="No subtitle file found for this video"
                )
            
            subtitle_path = str(subtitle_file)
        
        # Parse subtitles
        parser = TTSSRTParser()
        entries = parser.parse(Path(subtitle_path))
        
        if not entries:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="No subtitle entries found in file"
            )
        
        # Load TTS config for sentence merge settings
        config_mgr = get_config_manager()
        config_mgr.set_db_session(db)
        tts_config = await config_mgr.get_config("tts")
        
        # Check if sentence merge is enabled and configured
        enable_merge = getattr(tts_config, 'enable_sentence_merge', False)
        if not enable_merge:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Sentence merge is not enabled in TTS configuration"
            )
        
        # Get AI provider for sentence merge
        sentence_merge_provider_id = getattr(tts_config, 'sentence_merge_provider_id', None)
        if not sentence_merge_provider_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="No AI provider configured for sentence merge"
            )
        
        # Load AI provider
        from backend.core.repositories import AIProviderRepository
        from backend.core.encryption import get_encryption_manager
        from backend.core.config import get_system_settings
        
        ai_repo = AIProviderRepository(db)
        provider = await ai_repo.get_by_id(sentence_merge_provider_id)
        
        if not provider or not provider.is_enabled:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Sentence merge AI provider not found or disabled"
            )
        
        # Decrypt API key
        settings = get_system_settings()
        encryption = get_encryption_manager(settings.data_dir)
        
        try:
            api_key = encryption.decrypt(provider.api_key)
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt AI provider API key"
            )
        
        # Get base URL
        base_url = provider.base_url or {
            'deepseek': 'https://api.deepseek.com/v1',
            'openai': 'https://api.openai.com/v1',
            'openai_compatible': provider.base_url,
        }.get(provider.api_type.value, 'https://api.deepseek.com/v1')
        
        # Get merge settings
        merge_model = getattr(tts_config, 'sentence_merge_model', 'deepseek-chat')
        merge_temperature = getattr(tts_config, 'sentence_merge_temperature', 0.3)
        merge_system_prompt = getattr(tts_config, 'sentence_merge_system_prompt', None)
        merge_user_prompt = getattr(tts_config, 'sentence_merge_user_prompt', None)
        
        # Create merger and execute
        merger = SentenceMerger(
            api_key=api_key,
            base_url=base_url,
            model=merge_model,
            temperature=merge_temperature,
            system_prompt=merge_system_prompt,
            user_prompt=merge_user_prompt,
        )
        
        try:
            merged_entries = await merger.merge(entries)
        except SentenceMergeError as e:
            logger.error(f"Sentence merge failed: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sentence merge failed: {str(e)}"
            )
        
        # Build response
        original_response = [
            SubtitleEntryResponse(
                index=e.index,
                start_time=e.start_time,
                end_time=e.end_time,
                text=e.text,
            )
            for e in entries
        ]
        
        merged_response = [
            MergedEntryResponse(
                merged_text=m.merged_text,
                original_indices=m.original_indices,
                start_time=m.start_time,
                end_time=m.end_time,
            )
            for m in merged_entries
        ]
        
        return success_response(
            data={
                "original_entries": [e.model_dump() for e in original_response],
                "merged_entries": [m.model_dump() for m in merged_response],
                "original_count": len(entries),
                "merged_count": len(merged_entries),
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview sentence merge: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview sentence merge: {str(e)}"
        )


@router.post("/sentence-merge/adjust")
async def adjust_merged_entries(
    request: ManualMergeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually adjust merged entries.
    
    Actions:
    - merge: Merge two adjacent entries
    - split: Split an entry at a character position
    - edit: Edit the text of an entry
    """
    try:
        entries = request.entries
        action = request.action
        target_idx = request.target_index
        
        if target_idx < 0 or target_idx >= len(entries):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target index: {target_idx}"
            )
        
        result_entries = [e.model_dump() for e in entries]
        
        if action == "merge":
            # Merge with adjacent entry
            merge_idx = request.merge_with_index
            if merge_idx is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="merge_with_index is required for merge action"
                )
            
            if merge_idx < 0 or merge_idx >= len(entries):
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid merge_with_index: {merge_idx}"
                )
            
            # Ensure they are adjacent
            if abs(target_idx - merge_idx) != 1:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="Can only merge adjacent entries"
                )
            
            # Determine order
            first_idx = min(target_idx, merge_idx)
            second_idx = max(target_idx, merge_idx)
            
            first = result_entries[first_idx]
            second = result_entries[second_idx]
            
            # Create merged entry
            merged = {
                "merged_text": first["merged_text"] + second["merged_text"],
                "original_indices": first["original_indices"] + second["original_indices"],
                "start_time": first["start_time"],
                "end_time": second["end_time"],
            }
            
            # Replace first with merged, remove second
            result_entries[first_idx] = merged
            result_entries.pop(second_idx)
            
        elif action == "split":
            # Split entry at character position
            split_at = request.split_at_char
            if split_at is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="split_at_char is required for split action"
                )
            
            entry = result_entries[target_idx]
            text = entry["merged_text"]
            
            if split_at <= 0 or split_at >= len(text):
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid split position: {split_at}"
                )
            
            # Calculate time split based on character ratio
            total_duration = entry["end_time"] - entry["start_time"]
            ratio = split_at / len(text)
            split_time = entry["start_time"] + total_duration * ratio
            
            # Split original indices (approximate)
            orig_indices = entry["original_indices"]
            split_idx = max(1, int(len(orig_indices) * ratio))
            
            first_part = {
                "merged_text": text[:split_at],
                "original_indices": orig_indices[:split_idx] if split_idx < len(orig_indices) else orig_indices[:1],
                "start_time": entry["start_time"],
                "end_time": split_time,
            }
            
            second_part = {
                "merged_text": text[split_at:],
                "original_indices": orig_indices[split_idx:] if split_idx < len(orig_indices) else orig_indices[-1:],
                "start_time": split_time,
                "end_time": entry["end_time"],
            }
            
            # Replace entry with two parts
            result_entries[target_idx] = first_part
            result_entries.insert(target_idx + 1, second_part)
            
        elif action == "edit":
            # Edit text
            new_text = request.new_text
            if new_text is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="new_text is required for edit action"
                )
            
            result_entries[target_idx]["merged_text"] = new_text
            
        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {action}"
            )
        
        return success_response(
            data={
                "entries": result_entries,
                "count": len(result_entries),
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to adjust merged entries: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust merged entries: {str(e)}"
        )


@router.post("/voice-preview")
async def preview_voice(
    request: VoicePreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Preview a TTS voice by synthesizing a short text sample.
    
    Supports online TTS engines: azure_tts, edge_tts, volc_tts
    Returns audio as MP3 stream.
    """
    engine = request.engine
    voice = request.voice
    text = request.text or "你好，这是语音合成的试听效果。Hello, this is a voice preview."
    
    # Validate engine
    if engine not in ['azure_tts', 'edge_tts', 'volc_tts']:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Voice preview only supports online TTS engines: azure_tts, edge_tts, volc_tts"
        )
    
    try:
        audio_data = None
        
        if engine == 'edge_tts':
            # Edge TTS is free and doesn't require API key
            import edge_tts
            
            communicate = edge_tts.Communicate(text, voice)
            audio_buffer = io.BytesIO()
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            
            audio_buffer.seek(0)
            audio_data = audio_buffer.getvalue()
            
        elif engine == 'azure_tts':
            # Azure TTS uses free Microsoft Translator endpoint (no API key needed)
            from backend.services.tts import TTSConfig, AzureTTSEngine, TTSEngine
            from backend.core import get_config_manager
            
            # Get proxy from global config
            config_mgr = get_config_manager()
            config_mgr.set_db_session(db)
            global_config = await config_mgr.get_config("global", use_cache=False)
            proxy_url = getattr(global_config, 'proxy_url', None)
            
            # Create config with the selected voice and proxy
            config = TTSConfig(
                engine=TTSEngine.AZURE_TTS,
                azure_tts_voice=voice,
                proxy_url=proxy_url,
            )
            
            # Create engine and synthesize
            azure_engine = AzureTTSEngine(config)
            await azure_engine.load_model()
            
            audio_segment = await azure_engine.synthesize(text, speed=1.0, speaker=voice)
            
            # Convert to MP3 using ffmpeg
            import subprocess
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_path = wav_file.name
                # Write WAV header and data
                import wave
                with wave.open(wav_path, 'wb') as wf:
                    wf.setnchannels(audio_segment.channels)
                    wf.setsampwidth(audio_segment.sample_width)
                    wf.setframerate(audio_segment.sample_rate)
                    wf.writeframes(audio_segment.data)
            
            # Convert to MP3
            mp3_path = wav_path.replace('.wav', '.mp3')
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', wav_path,
                    '-acodec', 'libmp3lame', '-ab', '128k',
                    mp3_path
                ], check=True, capture_output=True)
                
                with open(mp3_path, 'rb') as f:
                    audio_data = f.read()
            finally:
                import os
                if os.path.exists(wav_path):
                    os.remove(wav_path)
                if os.path.exists(mp3_path):
                    os.remove(mp3_path)
                
        elif engine == 'volc_tts':
            # Volc TTS requires API key
            raise HTTPException(
                status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
                detail="Volc TTS voice preview not yet implemented"
            )
        
        if not audio_data:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate audio preview"
            )
        
        # Return audio as streaming response
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=preview.mp3"
            }
        )
        
    except HTTPException:
        raise
    except ImportError as e:
        logger.error(f"Missing dependency for voice preview: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing dependency: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to preview voice: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview voice: {str(e)}"
        )
