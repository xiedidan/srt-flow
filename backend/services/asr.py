"""
ASR (Automatic Speech Recognition) Service Module.

Provides speech recognition functionality using:
- Faster Whisper XXL (standalone executable)
- Gemini API (online)
to generate SRT subtitles.
"""
import asyncio
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.core.models import Task, FileType
from backend.core.logger import get_logger
from backend.workers.worker import BaseService, ProgressCallback


# ============================================================================
# Constants and Types
# ============================================================================

class ASREngine(str, Enum):
    """ASR engine options (matches config)."""
    FASTER_WHISPER_XXL = "faster_whisper_xxl"
    GEMINI = "gemini"


class ASRChannel(str, Enum):
    """ASR channel options (legacy, for compatibility)."""
    WHISPER_LOCAL = "whisper_local"
    GEMINI = "gemini"
    OPENAI = "openai"


class WhisperModel(str, Enum):
    """Whisper model sizes."""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"


class ComputeType(str, Enum):
    """Compute precision types."""
    FLOAT32 = "float32"
    FLOAT16 = "float16"
    INT8 = "int8"


# ============================================================================
# Exceptions
# ============================================================================

class ASRError(Exception):
    """Base ASR error."""
    pass


class AudioExtractionError(ASRError):
    """Audio extraction failed."""
    pass


class ModelLoadError(ASRError):
    """Model loading failed."""
    pass


class TranscriptionError(ASRError):
    """Transcription failed."""
    pass


class APIError(ASRError):
    """Online API error."""
    pass


# ============================================================================
# Configuration
# ============================================================================

class ASRConfig:
    """ASR service configuration."""
    
    def __init__(
        self,
        engine: ASREngine = ASREngine.FASTER_WHISPER_XXL,
        channel: ASRChannel = ASRChannel.WHISPER_LOCAL,
        whisper_model: WhisperModel = WhisperModel.LARGE_V3,
        whisper_device: str = "cuda",
        compute_type: ComputeType = ComputeType.FLOAT16,
        whisper_extra_args: str = "",
        language: str = "auto",
        beam_size: int = 5,
        vad_filter: bool = True,
        model_cache_dir: str = "data/models",
        online_provider: str = "gemini",
        gemini_api_key: Optional[str] = None,
        gemini_base_url: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        max_subtitle_chars: int = 80,
        max_subtitle_duration: float = 7.0,
        min_subtitle_duration: float = 1.0,
        ffmpeg_path: str = "ffmpeg",
    ):
        self.engine = engine
        self.channel = channel
        self.whisper_model = whisper_model
        self.whisper_device = whisper_device
        self.compute_type = compute_type
        self.whisper_extra_args = whisper_extra_args
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.model_cache_dir = model_cache_dir
        self.online_provider = online_provider
        self.gemini_api_key = gemini_api_key
        self.gemini_base_url = gemini_base_url
        self.openai_api_key = openai_api_key
        self.max_subtitle_chars = max_subtitle_chars
        self.max_subtitle_duration = max_subtitle_duration
        self.min_subtitle_duration = min_subtitle_duration
        self.ffmpeg_path = ffmpeg_path


# ============================================================================
# SRT Utilities
# ============================================================================

class SRTSegment:
    """Represents a single SRT subtitle segment."""
    
    def __init__(
        self,
        index: int,
        start: float,
        end: float,
        text: str,
    ):
        self.index = index
        self.start = start  # seconds
        self.end = end      # seconds
        self.text = text
    
    def to_srt(self) -> str:
        """Convert to SRT format string."""
        start_ts = self._format_timestamp(self.start)
        end_ts = self._format_timestamp(self.end)
        return f"{self.index}\n{start_ts} --> {end_ts}\n{self.text}\n"
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds to SRT timestamp (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class SRTGenerator:
    """Generates and optimizes SRT subtitle files."""
    
    def __init__(
        self,
        max_chars: int = 80,
        max_duration: float = 7.0,
        min_duration: float = 1.0,
        gap_duration: float = 0.1,
    ):
        self._max_chars = max_chars
        self._max_duration = max_duration
        self._min_duration = min_duration
        self._gap = gap_duration
        self._logger = get_logger("asr.srt")
    
    def generate(
        self,
        segments: List[Dict[str, Any]],
        output_path: Path,
    ) -> int:
        """
        Generate SRT file from segments.
        
        Args:
            segments: List of segment dicts with start, end, text
            output_path: Output file path
            
        Returns:
            Number of segments written
        """
        # Optimize segments
        optimized = self._optimize_segments(segments)
        
        # Write SRT file
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(optimized, 1):
                srt_seg = SRTSegment(i, seg["start"], seg["end"], seg["text"])
                f.write(srt_seg.to_srt())
                f.write("\n")
        
        self._logger.info(f"Generated SRT with {len(optimized)} segments")
        return len(optimized)

    def _optimize_segments(
        self,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Optimize segments for readability."""
        if not segments:
            return []
        
        optimized = []
        
        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue
            
            start = seg["start"]
            end = seg["end"]
            duration = end - start
            
            # Split long segments
            if len(text) > self._max_chars or duration > self._max_duration:
                split_segs = self._split_segment(start, end, text)
                optimized.extend(split_segs)
            else:
                optimized.append({"start": start, "end": end, "text": text})
        
        # Merge short segments
        optimized = self._merge_short_segments(optimized)
        
        # Ensure no overlap and add gaps
        optimized = self._fix_timestamps(optimized)
        
        return optimized
    
    def _split_segment(
        self,
        start: float,
        end: float,
        text: str,
    ) -> List[Dict[str, Any]]:
        """Split a long segment into smaller ones."""
        # Split by sentence boundaries first
        sentences = re.split(r'([.!?。！？]+)', text)
        
        # Reconstruct sentences with punctuation
        parts = []
        current = ""
        for i, s in enumerate(sentences):
            if re.match(r'^[.!?。！？]+$', s):
                current += s
                if current.strip():
                    parts.append(current.strip())
                current = ""
            else:
                if current.strip():
                    parts.append(current.strip())
                current = s
        if current.strip():
            parts.append(current.strip())
        
        # If still too long, split by comma or space
        final_parts = []
        for part in parts:
            if len(part) > self._max_chars:
                sub_parts = self._split_by_length(part)
                final_parts.extend(sub_parts)
            else:
                final_parts.append(part)
        
        if not final_parts:
            return [{"start": start, "end": end, "text": text}]
        
        # Distribute time proportionally
        total_chars = sum(len(p) for p in final_parts)
        duration = end - start
        
        result = []
        current_time = start
        for part in final_parts:
            part_duration = (len(part) / total_chars) * duration
            part_end = min(current_time + part_duration, end)
            result.append({
                "start": current_time,
                "end": part_end,
                "text": part,
            })
            current_time = part_end
        
        return result

    def _split_by_length(self, text: str) -> List[str]:
        """Split text by max length at word/comma boundaries."""
        parts = []
        
        # Try comma split first
        if ',' in text or '，' in text:
            chunks = re.split(r'[,，]', text)
            current = ""
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue
                if len(current) + len(chunk) + 1 <= self._max_chars:
                    current = f"{current}, {chunk}" if current else chunk
                else:
                    if current:
                        parts.append(current)
                    current = chunk
            if current:
                parts.append(current)
            return parts if parts else [text]
        
        # Split by space for English
        words = text.split()
        if len(words) > 1:
            current = ""
            for word in words:
                if len(current) + len(word) + 1 <= self._max_chars:
                    current = f"{current} {word}" if current else word
                else:
                    if current:
                        parts.append(current)
                    current = word
            if current:
                parts.append(current)
            return parts if parts else [text]
        
        # Force split for very long text without spaces
        while len(text) > self._max_chars:
            parts.append(text[:self._max_chars])
            text = text[self._max_chars:]
        if text:
            parts.append(text)
        
        return parts
    
    def _merge_short_segments(
        self,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Merge segments that are too short."""
        if not segments:
            return []
        
        merged = []
        current = segments[0].copy()
        
        for seg in segments[1:]:
            current_duration = current["end"] - current["start"]
            combined_text = f"{current['text']} {seg['text']}"
            combined_duration = seg["end"] - current["start"]
            
            # Merge if current is too short and combined is acceptable
            if (current_duration < self._min_duration and
                len(combined_text) <= self._max_chars and
                combined_duration <= self._max_duration):
                current["end"] = seg["end"]
                current["text"] = combined_text
            else:
                merged.append(current)
                current = seg.copy()
        
        merged.append(current)
        return merged
    
    def _fix_timestamps(
        self,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Fix overlapping timestamps and add gaps."""
        if not segments:
            return []
        
        fixed = []
        for i, seg in enumerate(segments):
            if i > 0:
                prev_end = fixed[-1]["end"]
                if seg["start"] < prev_end + self._gap:
                    seg["start"] = prev_end + self._gap
                if seg["start"] >= seg["end"]:
                    seg["end"] = seg["start"] + 0.5
            fixed.append(seg)
        
        return fixed


# ============================================================================
# Audio Extractor
# ============================================================================

class AudioExtractor:
    """Extracts audio from video files using FFmpeg."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self._ffmpeg = ffmpeg_path
        self._logger = get_logger("asr.audio")
        self._cancelled = False
    
    async def extract(
        self,
        video_path: Path,
        output_path: Path,
        sample_rate: int = 16000,
        mono: bool = True,
        force: bool = False,
    ) -> Path:
        """
        Extract audio from video file.
        
        Args:
            video_path: Input video path
            output_path: Output audio path
            sample_rate: Target sample rate (16kHz for Whisper)
            mono: Convert to mono
            force: Force re-extraction even if output exists
            
        Returns:
            Path to extracted audio
        """
        if output_path.exists() and not force:
            self._logger.info(f"Audio already exists: {output_path}")
            return output_path
        
        cmd = [
            self._ffmpeg,
            "-i", str(video_path),
            "-vn",  # No video
            "-acodec", "aac",
            "-ar", str(sample_rate),
        ]
        
        if mono:
            cmd.extend(["-ac", "1"])
        
        cmd.extend([
            "-b:a", "128k",
            "-y",  # Overwrite
            str(output_path),
        ])
        
        self._logger.info(f"Extracting audio: {video_path} -> {output_path}")
        self._cancelled = False
        
        # Run FFmpeg in thread pool (Windows compatible)
        import subprocess
        
        def _run_ffmpeg():
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
            )
            return result
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_ffmpeg)
        
        if self._cancelled:
            raise AudioExtractionError("Extraction cancelled")
        
        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="replace")
            raise AudioExtractionError(f"FFmpeg failed: {error_msg}")
        
        if not output_path.exists():
            raise AudioExtractionError("Output file not created")
        
        self._logger.info(f"Audio extracted successfully: {output_path}")
        return output_path
    
    async def cancel(self) -> bool:
        """Cancel ongoing extraction."""
        self._cancelled = True
        return True
    
    async def get_duration(self, file_path: Path) -> float:
        """Get audio/video duration in seconds."""
        import subprocess
        
        cmd = [
            self._ffmpeg,
            "-i", str(file_path),
            "-f", "null", "-"
        ]
        
        def _run():
            return subprocess.run(cmd, capture_output=True, text=False)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run)
        
        output = result.stderr.decode("utf-8", errors="replace")
        
        # Parse duration from FFmpeg output
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
        if match:
            hours, mins, secs, centis = map(int, match.groups())
            return hours * 3600 + mins * 60 + secs + centis / 100
        
        return 0.0


# ============================================================================
# Whisper Local Transcriber
# ============================================================================

class WhisperTranscriber:
    """
    Local Whisper transcription using faster-whisper.
    
    Uses singleton pattern to avoid reloading model.
    """
    
    _instance: Optional["WhisperTranscriber"] = None
    _model = None
    _model_name: Optional[str] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        model_size: WhisperModel = WhisperModel.LARGE_V3,
        device: str = "cuda",
        compute_type: ComputeType = ComputeType.FLOAT16,
        cache_dir: str = "data/models",
    ):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._cache_dir = cache_dir
        self._logger = get_logger("asr.whisper")
        self._cancelled = False
    
    def _load_model(self) -> None:
        """Load Whisper model if not already loaded."""
        model_name = self._model_size.value
        
        if WhisperTranscriber._model is not None and WhisperTranscriber._model_name == model_name:
            self._logger.info(f"Reusing loaded model: {model_name}")
            return
        
        self._logger.info(f"Loading Whisper model: {model_name}")
        
        try:
            from faster_whisper import WhisperModel
            
            # Check device availability
            device = self._device
            if device == "cuda":
                try:
                    import torch
                    if not torch.cuda.is_available():
                        self._logger.warning("CUDA not available, falling back to CPU")
                        device = "cpu"
                except ImportError:
                    device = "cpu"
            
            compute_type = self._compute_type.value
            if device == "cpu" and compute_type == "float16":
                compute_type = "float32"
            
            WhisperTranscriber._model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=self._cache_dir,
            )
            WhisperTranscriber._model_name = model_name
            
            self._logger.info(f"Model loaded: {model_name} on {device}")
            
        except Exception as e:
            self._logger.error(f"Failed to load model: {e}")
            raise ModelLoadError(f"Failed to load Whisper model: {e}")

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        beam_size: int = 5,
        vad_filter: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Transcribe audio file.
        
        Args:
            audio_path: Path to audio file
            language: Source language or "auto"
            beam_size: Beam search size
            vad_filter: Enable VAD filtering
            progress_callback: Progress callback
            
        Returns:
            Tuple of (segments list, detected language)
        """
        self._cancelled = False
        self._load_model()
        
        self._logger.info(f"Transcribing: {audio_path}")
        
        # Run transcription in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        def _transcribe():
            lang = None if language == "auto" else language
            
            segments, info = WhisperTranscriber._model.transcribe(
                str(audio_path),
                language=lang,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=False,
            )
            
            result_segments = []
            total_duration = info.duration
            
            for seg in segments:
                if self._cancelled:
                    break
                
                result_segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                })
                
                # Report progress
                if progress_callback and total_duration > 0:
                    progress = int((seg.end / total_duration) * 80) + 10
                    progress_callback(min(progress, 90))
            
            return result_segments, info.language
        
        try:
            segments, detected_lang = await loop.run_in_executor(None, _transcribe)
            self._logger.info(f"Transcription complete: {len(segments)} segments, lang={detected_lang}")
            return segments, detected_lang
        except Exception as e:
            self._logger.error(f"Transcription failed: {e}")
            raise TranscriptionError(f"Whisper transcription failed: {e}")
    
    def cancel(self) -> None:
        """Cancel ongoing transcription."""
        self._cancelled = True


# ============================================================================
# Faster Whisper XXL Transcriber (Standalone Executable)
# ============================================================================

class FasterWhisperXXLTranscriber:
    """
    Transcription using Faster Whisper XXL standalone executable.
    
    This uses the pre-built executable from:
    https://github.com/Purfview/whisper-standalone-win
    """
    
    def __init__(
        self,
        model_size: str = "large-v3",
        model_dir: str = "data/models",
        device: str = "auto",
        extra_args: str = "",
    ):
        self._model_size = model_size
        self._model_dir = Path(model_dir)
        self._device = device
        self._extra_args = extra_args
        self._logger = get_logger("asr.faster_whisper_xxl")
        self._cancelled = False
        self._process: Optional[subprocess.Popen] = None
    
    def _get_executable_path(self) -> Path:
        """Get path to faster-whisper-xxl executable."""
        system = platform.system().lower()
        if system == "windows":
            plat = "windows"
            exe_name = "faster-whisper-xxl.exe"
        else:
            plat = "linux"
            exe_name = "faster-whisper-xxl"
        
        engine_dir = self._model_dir / f"faster_whisper_xxl-{plat}"
        
        # Check in root
        exe_path = engine_dir / exe_name
        if exe_path.exists():
            return exe_path
        
        # Search recursively (some archives extract to subdirectory)
        for root, dirs, files in os.walk(engine_dir):
            if exe_name in files:
                return Path(root) / exe_name
        
        raise ModelLoadError(
            f"Faster Whisper XXL executable not found. "
            f"Please download it from Settings -> ASR -> Engine Download"
        )
    
    def _get_model_path(self) -> Path:
        """Get path to Whisper model."""
        model_path = self._model_dir / f"faster-whisper-{self._model_size}"
        if not model_path.exists():
            raise ModelLoadError(
                f"Whisper model '{self._model_size}' not found. "
                f"Please download it from Settings -> ASR -> Model Download"
            )
        return model_path
    
    async def transcribe(
        self,
        audio_path: Path,
        output_dir: Path,
        language: str = "auto",
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Transcribe audio file using faster-whisper-xxl executable.
        
        Args:
            audio_path: Path to audio file
            output_dir: Directory for output SRT file
            language: Source language or "auto"
            progress_callback: Progress callback
            
        Returns:
            Tuple of (segments list, detected language)
        """
        self._cancelled = False
        
        exe_path = self._get_executable_path()
        model_path = self._get_model_path()
        
        self._logger.info(f"Using executable: {exe_path}")
        self._logger.info(f"Using model: {model_path}")
        
        # Build command for faster-whisper-xxl
        # Reference: https://github.com/Purfview/whisper-standalone-win
        cmd = [
            str(exe_path),
            str(audio_path),
            "--model_dir", str(model_path),
            "--output_dir", str(output_dir),
            "--output_format", "srt",
        ]
        
        # Add language if specified
        if language and language != "auto":
            cmd.extend(["--language", language])
        
        # Add device setting
        if self._device == "cpu":
            cmd.extend(["--device", "cpu"])
        elif self._device == "cuda":
            cmd.extend(["--device", "cuda"])
        # "auto" lets the tool decide
        
        # Add extra arguments from config (filter out --language if already set)
        if self._extra_args:
            extra_parts = self._extra_args.split()
            # Remove any existing --language from extra_args to avoid duplication
            filtered_parts = []
            skip_next = False
            for i, part in enumerate(extra_parts):
                if skip_next:
                    skip_next = False
                    continue
                if part == "--language":
                    skip_next = True  # Skip the next part (language value)
                    continue
                filtered_parts.append(part)
            cmd.extend(filtered_parts)
        
        self._logger.info(f"Running command: {' '.join(cmd)}")
        
        if progress_callback:
            progress_callback(15)
        
        # Run in thread pool
        loop = asyncio.get_event_loop()
        
        def _run():
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            
            output_lines = []
            last_progress = 15
            
            # Read output line by line for progress
            for line in iter(self._process.stdout.readline, ""):
                if self._cancelled:
                    self._process.terminate()
                    raise TranscriptionError("Transcription cancelled")
                
                output_lines.append(line)
                self._logger.debug(line.strip())
                
                # Parse progress from output (e.g., "[00:01:30 --> 00:01:35]")
                time_match = re.search(r'\[(\d+):(\d+):(\d+)', line)
                if time_match and progress_callback:
                    # Estimate progress based on timestamp
                    h, m, s = map(int, time_match.groups())
                    current_time = h * 3600 + m * 60 + s
                    # Assume max 2 hours, scale to 15-85%
                    progress = min(85, 15 + int(current_time / 7200 * 70))
                    if progress > last_progress:
                        last_progress = progress
                        progress_callback(progress)
            
            self._process.wait()
            return self._process.returncode, "".join(output_lines)
        
        try:
            returncode, output = await loop.run_in_executor(None, _run)
        finally:
            self._process = None
        
        # Log output for debugging
        self._logger.info(f"Faster Whisper XXL output:\n{output}")
        
        if progress_callback:
            progress_callback(85)
        
        # Find the generated SRT file FIRST (before checking return code)
        # Sometimes the process crashes during cleanup but output is already written
        srt_file = None
        possible_names = [
            output_dir / f"{audio_path.stem}.srt",
            output_dir / "audio_original.srt",
            output_dir / f"{audio_path.name}.srt",
        ]
        
        for candidate in possible_names:
            if candidate.exists():
                srt_file = candidate
                self._logger.info(f"Found SRT file: {srt_file}")
                break
        
        # If not found, search for any new SRT file
        if not srt_file:
            self._logger.info(f"Searching for SRT files in {output_dir}")
            for f in output_dir.glob("*.srt"):
                self._logger.info(f"Found: {f}")
                if f.name != "subtitle_original.srt":
                    srt_file = f
                    break
        
        # Check return code - but if SRT exists, treat certain crash codes as success
        if returncode != 0:
            # Check if output indicates success despite crash
            output_success = "Operation finished" in output or "Subtitles are written" in output
            srt_exists = srt_file is not None and srt_file.exists()
            
            # These crash codes often happen during cleanup after successful transcription
            cleanup_crash_codes = [
                3221226505, -1073740791,  # 0xC0000409 STATUS_STACK_BUFFER_OVERRUN
                3221225477, -1073741819,  # 0xC0000005 ACCESS_VIOLATION
            ]
            
            if srt_exists and (output_success or returncode in cleanup_crash_codes):
                # SRT file exists and output indicates success - treat as success with warning
                self._logger.warning(
                    f"Process exited with code {returncode} but SRT file was generated. "
                    f"This is likely a cleanup crash, treating as success."
                )
            else:
                # Real failure
                self._logger.error(f"Transcription failed with code {returncode}")
                
                # Provide user-friendly error messages for common error codes
                error_msg = f"Faster Whisper XXL failed with code {returncode}"
                
                # Windows error codes
                if returncode in [3221226505, -1073740791]:  # 0xC0000409 STATUS_STACK_BUFFER_OVERRUN
                    error_msg = (
                        "语音识别程序崩溃 (栈溢出)。可能原因：\n"
                        "1. GPU 显存不足，请尝试使用较小的模型或切换到 CPU 模式\n"
                        "2. 文件路径包含特殊字符，请尝试重命名视频\n"
                        "3. CUDA 驱动版本不兼容，请更新显卡驱动"
                    )
                elif returncode in [3221225477, -1073741819]:  # 0xC0000005 ACCESS_VIOLATION
                    error_msg = "语音识别程序崩溃 (内存访问错误)。请尝试重启应用或使用 CPU 模式"
                elif returncode in [3221225786, -1073741510]:  # 0xC000013A CTRL_C
                    error_msg = "语音识别被用户中断"
                elif "CUDA" in output.upper() or "GPU" in output.upper():
                    error_msg = f"GPU/CUDA 错误。请检查显卡驱动或尝试 CPU 模式。\n详情: {output[-500:]}"
                elif "out of memory" in output.lower():
                    error_msg = "GPU 显存不足。请尝试使用较小的模型 (如 medium) 或切换到 CPU 模式"
                else:
                    error_msg = f"{error_msg}\n输出: {output[-1000:] if len(output) > 1000 else output}"
                
                raise TranscriptionError(error_msg)
        
        if not srt_file or not srt_file.exists():
            # List all files in directory for debugging
            all_files = list(output_dir.iterdir())
            self._logger.error(f"SRT not found. Files in {output_dir}: {[f.name for f in all_files]}")
            raise TranscriptionError(f"SRT file not generated. Check if model and engine are properly installed.")
        
        # Parse SRT to segments
        segments = self._parse_srt(srt_file)
        
        # Detect language from output or default
        detected_lang = "unknown"
        lang_match = re.search(r'Detected language[:\s]+(\w+)', output, re.IGNORECASE)
        if lang_match:
            detected_lang = lang_match.group(1).lower()
        elif language != "auto":
            detected_lang = language
        
        self._logger.info(f"Transcription complete: {len(segments)} segments")
        
        # Clean up intermediate SRT if different from target
        if srt_file.name != "subtitle_original.srt":
            # Move to standard name
            target_srt = output_dir / "subtitle_original.srt"
            if srt_file != target_srt:
                import shutil
                shutil.move(str(srt_file), str(target_srt))
        
        return segments, detected_lang
    
    def _parse_srt(self, srt_path: Path) -> List[Dict[str, Any]]:
        """Parse SRT file to segment list."""
        segments = []
        
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Split by double newline (SRT entries)
        entries = re.split(r'\n\n+', content.strip())
        
        for entry in entries:
            lines = entry.strip().split('\n')
            if len(lines) < 3:
                continue
            
            # Parse timestamp line
            time_match = re.match(
                r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)',
                lines[1]
            )
            if not time_match:
                continue
            
            h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, time_match.groups())
            start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
            end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
            
            # Join remaining lines as text
            text = '\n'.join(lines[2:]).strip()
            
            segments.append({
                "start": start,
                "end": end,
                "text": text,
            })
        
        return segments
    
    def cancel(self) -> None:
        """Cancel ongoing transcription."""
        self._cancelled = True
        if self._process:
            self._process.terminate()


# ============================================================================
# Online API Transcribers
# ============================================================================

class OnlineTranscriber:
    """Base class for online transcription APIs."""
    
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._logger = get_logger("asr.online")
    
    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Transcribe audio using online API."""
        raise NotImplementedError


class OpenAITranscriber(OnlineTranscriber):
    """OpenAI Whisper API transcriber."""
    
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
    
    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Transcribe using OpenAI Whisper API."""
        try:
            import httpx
        except ImportError:
            raise ASRError("httpx is required for OpenAI API")
        
        file_size = audio_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            self._logger.warning(f"File too large ({file_size}), may need chunking")
        
        if progress_callback:
            progress_callback(10)
        
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (audio_path.name, f, "audio/m4a")}
                data = {
                    "model": "whisper-1",
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                }
                if language != "auto":
                    data["language"] = language
                
                if progress_callback:
                    progress_callback(30)
                
                response = await client.post(url, headers=headers, files=files, data=data)
        
        if response.status_code != 200:
            raise APIError(f"OpenAI API error: {response.status_code} - {response.text}")
        
        if progress_callback:
            progress_callback(80)
        
        result = response.json()
        segments = []
        
        for seg in result.get("segments", []):
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            })
        
        detected_lang = result.get("language", "unknown")
        
        if progress_callback:
            progress_callback(90)
        
        return segments, detected_lang


class GeminiTranscriber(OnlineTranscriber):
    """Google Gemini API transcriber."""
    
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key)
        self._base_url = base_url.rstrip('/') if base_url else self.DEFAULT_BASE_URL
    
    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Transcribe using Gemini API."""
        try:
            import httpx
            import base64
        except ImportError:
            raise ASRError("httpx is required for Gemini API")
        
        if progress_callback:
            progress_callback(10)
        
        # Read and encode audio
        with open(audio_path, "rb") as f:
            audio_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        if progress_callback:
            progress_callback(20)
        
        # Prepare request - support custom base URL for third-party services
        url = f"{self._base_url}/models/gemini-1.5-flash:generateContent?key={self._api_key}"
        
        prompt = """Transcribe this audio file with timestamps. 
Output format: JSON array with objects containing "start" (seconds), "end" (seconds), "text" fields.
Example: [{"start": 0.0, "end": 2.5, "text": "Hello world"}]
Only output the JSON array, no other text."""
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "audio/m4a",
                            "data": audio_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192,
            }
        }
        
        if progress_callback:
            progress_callback(30)
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json=payload)
        
        if response.status_code != 200:
            raise APIError(f"Gemini API error: {response.status_code} - {response.text}")
        
        if progress_callback:
            progress_callback(80)
        
        result = response.json()
        
        # Parse response
        try:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                segments = json.loads(json_match.group())
            else:
                raise APIError("No valid JSON in Gemini response")
        except (KeyError, json.JSONDecodeError) as e:
            raise APIError(f"Failed to parse Gemini response: {e}")
        
        if progress_callback:
            progress_callback(90)
        
        # Gemini doesn't reliably detect language
        detected_lang = language if language != "auto" else "unknown"
        
        return segments, detected_lang


# ============================================================================
# ASR Service
# ============================================================================

class ASRService(BaseService):
    """
    Automatic Speech Recognition service.
    
    Implements BaseService interface for worker integration.
    Supports Faster Whisper XXL (local) and Gemini API (online).
    
    Configuration is loaded from database at runtime.
    """
    
    def __init__(self, config: Optional[ASRConfig] = None):
        """
        Initialize ASR service.
        
        Args:
            config: ASR configuration (fallback, actual config loaded from DB)
        """
        self._config = config or ASRConfig()
        self._logger = get_logger("asr")
        self._audio_extractor = AudioExtractor(self._config.ffmpeg_path)
        self._srt_generator = SRTGenerator(
            max_chars=self._config.max_subtitle_chars,
            max_duration=self._config.max_subtitle_duration,
            min_duration=self._config.min_subtitle_duration,
        )
        self._current_task_id: Optional[str] = None
        self._xxl_transcriber: Optional[FasterWhisperXXLTranscriber] = None
    
    async def _load_config_from_db(self, session=None) -> dict:
        """Load ASR configuration from database.
        
        Args:
            session: Optional existing database session to reuse
        """
        from backend.core.config import get_config_manager
        from backend.core.database import get_database_manager
        
        config_manager = get_config_manager()
        
        async def _do_load(sess):
            config_manager.set_db_session(sess)
            
            # Load ASR config
            asr_config = await config_manager.get_config("asr")
            
            # Load API key if using Gemini
            gemini_api_key = None
            if asr_config.engine.value == "gemini":
                gemini_api_key = await config_manager.get_api_key("asr", "gemini_api_key")
            
            return {
                "engine": asr_config.engine.value,
                "model_size": asr_config.whisper_model_size.value,
                "device": asr_config.device.value,
                "extra_args": asr_config.whisper_extra_args,
                "gemini_api_key": gemini_api_key,
                "gemini_base_url": asr_config.gemini_base_url,
            }
        
        if session:
            return await _do_load(session)
        else:
            db_manager = get_database_manager()
            async with db_manager.session() as new_session:
                return await _do_load(new_session)
    
    async def execute(
        self,
        task: Task,
        progress_callback: ProgressCallback,
        payload_callback=None,
        session=None,
    ) -> Dict[str, Any]:
        """
        Execute ASR task.
        
        Args:
            task: ASR task
            progress_callback: Progress callback
            payload_callback: Optional callback to update task payload (unused)
            session: Optional database session to reuse
            
        Returns:
            ASR result
        """
        self._current_task_id = task.id
        payload = task.payload or {}
        
        video_id = payload.get("video_id")
        video_path = payload.get("video_path")
        
        if not video_path:
            raise ASRError("video_path is required")
        
        video_path = Path(video_path)
        if not video_path.exists():
            raise ASRError(f"Video file not found: {video_path}")
        
        # Use pre-loaded config from payload if available (avoids greenlet issues)
        # Otherwise load from database (for direct API calls)
        if "_db_config" in payload:
            db_config = payload["_db_config"]
            self._logger.info("Using pre-loaded config from payload")
        else:
            db_config = await self._load_config_from_db(session)
        
        engine = db_config["engine"]
        model_size = payload.get("model", db_config["model_size"])
        
        # Get language from task payload, fallback to pre-loaded default or auto
        language = payload.get("language")
        if not language or language == "auto":
            language = payload.get("_default_language", "auto")
        
        self._logger.info(f"ASR engine: {engine}, model: {model_size}")
        
        video_dir = video_path.parent
        audio_path = video_dir / "audio_original.m4a"
        subtitle_path = video_dir / "subtitle_original.srt"
        
        try:
            # Stage 1: Extract audio (0-10%)
            progress_callback(0)
            self._logger.info(f"Extracting audio from: {video_path}")
            
            # Always force re-extraction to ensure audio completeness
            await self._audio_extractor.extract(video_path, audio_path, force=True)
            progress_callback(10)
            
            # Get audio duration
            duration = await self._audio_extractor.get_duration(audio_path)
            
            # Stage 2: Transcribe (10-90%)
            self._logger.info(f"Transcribing with engine: {engine}")
            
            if engine == "faster_whisper_xxl":
                segments, detected_lang = await self._transcribe_xxl(
                    audio_path, video_dir, language, model_size,
                    db_config["device"], db_config["extra_args"],
                    progress_callback
                )
            elif engine == "gemini":
                segments, detected_lang = await self._transcribe_gemini(
                    audio_path, language,
                    db_config["gemini_api_key"], db_config["gemini_base_url"],
                    progress_callback
                )
            else:
                raise ASRError(f"Unknown ASR engine: {engine}")
            
            progress_callback(90)
            
            # Stage 3: Generate/optimize SRT (90-100%)
            # For XXL, SRT is already generated, just count segments
            if engine == "faster_whisper_xxl" and subtitle_path.exists():
                segments_count = len(segments)
                self._logger.info(f"SRT already generated with {segments_count} segments")
            else:
                self._logger.info(f"Generating SRT: {subtitle_path}")
                segments_count = self._srt_generator.generate(segments, subtitle_path)
            
            progress_callback(100)
            
            return {
                "video_id": video_id,
                "audio_path": str(audio_path),
                "subtitle_path": str(subtitle_path),
                "language_detected": detected_lang,
                "duration": duration,
                "segments_count": segments_count,
            }
            
        finally:
            self._current_task_id = None

    async def _transcribe_xxl(
        self,
        audio_path: Path,
        output_dir: Path,
        language: str,
        model_size: str,
        device: str,
        extra_args: str,
        progress_callback: ProgressCallback,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Transcribe using Faster Whisper XXL executable."""
        self._xxl_transcriber = FasterWhisperXXLTranscriber(
            model_size=model_size,
            model_dir=self._config.model_cache_dir,
            device=device,
            extra_args=extra_args,
        )
        
        return await self._xxl_transcriber.transcribe(
            audio_path,
            output_dir,
            language=language,
            progress_callback=progress_callback,
        )
    
    async def _transcribe_gemini(
        self,
        audio_path: Path,
        language: str,
        api_key: Optional[str],
        base_url: Optional[str],
        progress_callback: ProgressCallback,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Transcribe using Gemini API."""
        if not api_key:
            raise ASRError("Gemini API key not configured. Please set it in Settings -> ASR")
        
        transcriber = GeminiTranscriber(api_key, base_url=base_url)
        
        return await transcriber.transcribe(
            audio_path,
            language=language,
            progress_callback=progress_callback,
        )
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel ASR task."""
        if self._current_task_id != task_id:
            return False
        
        # Cancel audio extraction
        await self._audio_extractor.cancel()
        
        # Cancel XXL transcription
        if self._xxl_transcriber:
            self._xxl_transcriber.cancel()
        
        return True
    
    def can_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        error_str = str(error).lower()
        
        # Non-retryable errors
        non_retryable = [
            "file not found",
            "video file not found",
            "api key not configured",
            "cuda out of memory",
            "out of memory",
        ]
        if any(msg in error_str for msg in non_retryable):
            return False
        
        # Retryable errors
        retryable = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "api error: 5",
            "api error: 429",
            "temporary",
        ]
        return any(msg in error_str for msg in retryable)
    
    # Utility methods for external use
    async def extract_audio(
        self,
        video_path: Path,
        output_path: Path,
    ) -> Path:
        """Extract audio from video file."""
        return await self._audio_extractor.extract(video_path, output_path)
    
    def generate_srt(
        self,
        segments: List[Dict[str, Any]],
        output_path: Path,
    ) -> int:
        """Generate SRT file from segments."""
        return self._srt_generator.generate(segments, output_path)
