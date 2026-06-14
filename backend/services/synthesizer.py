"""
Video Synthesizer Service Module.

Provides video synthesis functionality using FFmpeg for subtitle
burning and audio track replacement with hardware acceleration support.
"""
import asyncio
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.core.models import Task
from backend.core.logger import get_logger
from backend.workers.worker import BaseService, ProgressCallback


# ============================================================================
# Constants and Types
# ============================================================================

class AudioMode(str, Enum):
    """Audio mode options."""
    ORIGINAL = "original"  # Keep original audio
    TTS = "tts"  # Replace with TTS audio
    MIX = "mix"  # Mix original + TTS audio


class SubtitleMode(str, Enum):
    """Subtitle burning modes."""
    ORIGINAL_ONLY = "original_only"
    TRANSLATED_ONLY = "translated_only"
    DUAL = "dual"


class VideoCodec(str, Enum):
    """Video codec options."""
    H264 = "h264"
    H265 = "h265"
    AV1 = "av1"


class HardwareAccel(str, Enum):
    """Hardware acceleration options."""
    NONE = "none"
    CUDA = "cuda"
    VAAPI = "vaapi"
    QSV = "qsv"


class SubtitlePosition(str, Enum):
    """Subtitle position options."""
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


# ============================================================================
# Exceptions
# ============================================================================

class SynthesizerError(Exception):
    """Base synthesizer error."""
    pass


class FFmpegError(SynthesizerError):
    """FFmpeg execution error."""
    pass


class InputFileError(SynthesizerError):
    """Input file not found or invalid."""
    pass


class EncoderError(SynthesizerError):
    """Encoder not available."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SubtitleStyle:
    """Subtitle style configuration."""
    font_name: str = "Microsoft YaHei"
    font_size: int = 24
    font_bold: bool = False
    font_color: str = "#FFFFFF"
    font_alpha: float = 1.0
    outline_width: int = 2
    outline_color: str = "#000000"
    shadow_enabled: bool = True
    shadow_color: str = "#000000"
    shadow_offset: int = 2
    position: SubtitlePosition = SubtitlePosition.BOTTOM
    margin_v: int = 30
    margin_h: int = 20
    background_enabled: bool = False
    background_color: str = "#000000"
    background_alpha: float = 0.5
    
    def to_ass_style(self) -> str:
        """Convert to ASS style string for FFmpeg subtitles filter."""
        # Convert hex color to ASS format (BGR)
        primary_color = self._hex_to_ass_color(self.font_color, self.font_alpha)
        outline_color = self._hex_to_ass_color(self.outline_color, 1.0)
        shadow_color = self._hex_to_ass_color(self.shadow_color, 0.5 if self.shadow_enabled else 0)
        
        # Build force_style string
        style_parts = [
            f"FontName={self.font_name}",
            f"FontSize={self.font_size}",
            f"Bold={1 if self.font_bold else 0}",
            f"PrimaryColour={primary_color}",
            f"OutlineColour={outline_color}",
            f"Outline={self.outline_width}",
            f"Shadow={self.shadow_offset if self.shadow_enabled else 0}",
            f"MarginV={self.margin_v}",
            f"MarginL={self.margin_h}",
            f"MarginR={self.margin_h}",
        ]
        
        # Background box support
        # BorderStyle: 1 = outline + shadow (default), 3 = opaque box, 4 = shadow only
        if self.background_enabled:
            # Use BorderStyle=4 for background box (uses BackColour as background)
            back_color = self._hex_to_ass_color(self.background_color, self.background_alpha)
            style_parts.append("BorderStyle=4")
            style_parts.append(f"BackColour={back_color}")
        else:
            style_parts.append(f"BackColour={shadow_color}")
        
        # Position alignment
        alignment_map = {
            SubtitlePosition.TOP: 8,      # Top center
            SubtitlePosition.CENTER: 5,   # Middle center
            SubtitlePosition.BOTTOM: 2,   # Bottom center
        }
        style_parts.append(f"Alignment={alignment_map.get(self.position, 2)}")
        
        return ",".join(style_parts)
    
    def to_ass_style_escaped(self) -> str:
        """Convert to ASS style string with escaped commas for FFmpeg filter."""
        style = self.to_ass_style()
        # Escape commas for FFmpeg filter parsing
        return style.replace(",", "\\,")
    
    def _hex_to_ass_color(self, hex_color: str, alpha: float) -> str:
        """Convert hex color to ASS color format (&HAABBGGRR)."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        a = int((1 - alpha) * 255)
        return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


@dataclass
class StylePreset:
    """Subtitle style preset."""
    name: str
    description: str
    primary_style: SubtitleStyle
    secondary_style: Optional[SubtitleStyle] = None
    is_system: bool = False


@dataclass
class SynthesizerConfig:
    """Video synthesizer configuration."""
    subtitle_mode: SubtitleMode = SubtitleMode.DUAL
    audio_mode: AudioMode = AudioMode.ORIGINAL
    video_codec: VideoCodec = VideoCodec.H264
    video_crf: int = 23
    video_preset: str = "medium"
    use_hardware_encoder: bool = True
    hardware_accel: HardwareAccel = HardwareAccel.NONE
    audio_codec: str = "aac"
    audio_bitrate: str = "320k"
    output_format: str = "mp4"
    primary_style: SubtitleStyle = field(default_factory=SubtitleStyle)
    secondary_style: SubtitleStyle = field(default_factory=lambda: SubtitleStyle(
        font_size=18,
        font_color="#FFFACD",
        margin_v=60,
    ))
    ffmpeg_path: str = "ffmpeg"


# Default style presets
DEFAULT_PRESETS = {
    "default": StylePreset(
        name="default",
        description="Default dual subtitle style",
        primary_style=SubtitleStyle(font_color="#FFFFFF", font_size=24),
        secondary_style=SubtitleStyle(font_color="#FFFACD", font_size=18, margin_v=60),
        is_system=True,
    ),
    "youtube": StylePreset(
        name="youtube",
        description="YouTube-like subtitle style",
        primary_style=SubtitleStyle(
            font_name="Arial",
            font_size=22,
            font_color="#FFFFFF",
            outline_width=1,
            background_enabled=True,
            background_alpha=0.75,
        ),
        is_system=True,
    ),
    "netflix": StylePreset(
        name="netflix",
        description="Netflix-like subtitle style",
        primary_style=SubtitleStyle(
            font_name="Netflix Sans",
            font_size=26,
            font_color="#FFFFFF",
            outline_width=0,
            shadow_enabled=True,
            shadow_offset=3,
        ),
        is_system=True,
    ),
    "minimal": StylePreset(
        name="minimal",
        description="Minimal style without effects",
        primary_style=SubtitleStyle(
            font_size=22,
            font_color="#FFFFFF",
            outline_width=0,
            shadow_enabled=False,
        ),
        is_system=True,
    ),
    "high_contrast": StylePreset(
        name="high_contrast",
        description="High contrast for complex backgrounds",
        primary_style=SubtitleStyle(
            font_size=26,
            font_color="#FFFF00",
            outline_width=3,
            outline_color="#000000",
            shadow_enabled=True,
        ),
        is_system=True,
    ),
}


# ============================================================================
# Progress Parser
# ============================================================================

class FFmpegProgressParser:
    """Parses FFmpeg output for progress information."""
    
    # Pattern: time=00:01:23.45
    TIME_PATTERN = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})')
    # Pattern: speed=1.5x
    SPEED_PATTERN = re.compile(r'speed=\s*([\d.]+)x')
    # Pattern: size=1234kB
    SIZE_PATTERN = re.compile(r'size=\s*(\d+)kB')
    
    @classmethod
    def parse_line(cls, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse FFmpeg progress line.
        
        Args:
            line: FFmpeg stderr output line
            
        Returns:
            Progress info dict or None
        """
        time_match = cls.TIME_PATTERN.search(line)
        if not time_match:
            return None
        
        # Parse time to seconds
        h, m, s, cs = map(int, time_match.groups())
        current_time = h * 3600 + m * 60 + s + cs / 100
        
        result = {"current_time": current_time}
        
        # Parse speed
        speed_match = cls.SPEED_PATTERN.search(line)
        if speed_match:
            result["speed"] = float(speed_match.group(1))
        
        # Parse size
        size_match = cls.SIZE_PATTERN.search(line)
        if size_match:
            result["size_kb"] = int(size_match.group(1))
        
        return result


# ============================================================================
# FFmpeg Command Builder
# ============================================================================

class FFmpegCommandBuilder:
    """Builds FFmpeg commands for video synthesis."""
    
    def __init__(self, config: SynthesizerConfig):
        self._config = config
        self._logger = get_logger("synthesizer.ffmpeg")
    
    def build_synthesis_command(
        self,
        video_path: Path,
        output_path: Path,
        original_subtitle: Optional[Path] = None,
        translated_subtitle: Optional[Path] = None,
        tts_audio: Optional[Path] = None,
        audio_mode: AudioMode = AudioMode.ORIGINAL,
    ) -> List[str]:
        """
        Build FFmpeg command for video synthesis.
        
        Args:
            video_path: Input video path
            output_path: Output video path
            original_subtitle: Original subtitle path
            translated_subtitle: Translated subtitle path
            tts_audio: TTS audio path
            audio_mode: Audio processing mode
            
        Returns:
            FFmpeg command as list of arguments
        """
        cmd = [self._config.ffmpeg_path]
        
        # Build filter complex for subtitles first to check if we need it
        filter_complex = self._build_subtitle_filter(
            video_path, original_subtitle, translated_subtitle
        )
        
        # Hardware acceleration input
        # Note: When using subtitle filters (CPU-based), we cannot use hwaccel_output_format
        # because subtitle filters cannot process CUDA/GPU frames directly.
        # The decoded frames need to be in CPU memory for subtitle rendering.
        # NVENC encoder will automatically upload frames to GPU for encoding.
        if self._config.hardware_accel == HardwareAccel.CUDA:
            if filter_complex:
                # Only use hwaccel for decoding, output to CPU for subtitle processing
                cmd.extend(["-hwaccel", "cuda"])
            else:
                # No filters, can use full GPU pipeline
                cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
        elif self._config.hardware_accel == HardwareAccel.QSV:
            cmd.extend(["-hwaccel", "qsv"])
        elif self._config.hardware_accel == HardwareAccel.VAAPI:
            cmd.extend(["-hwaccel", "vaapi"])
        
        # Input video
        video_str = str(video_path)
        # Input video - use relative path for cwd to work
        # Get relative path from project root
        try:
            video_str = Path(video_path).relative_to(Path("E:/project/srt-flow"))
            video_str = str(video_str).replace("\\", "/")
        except ValueError:
            video_str = str(video_path)
        if os.name == 'nt' and "'" in video_str:
            video_str = self._get_short_path(video_str)
        cmd.extend(["-i", video_str])
        
        # Input TTS audio if needed
        audio_input_index = 0  # Video audio stream index
        if tts_audio and audio_mode in [AudioMode.TTS, AudioMode.MIX]:
            try:
                tts_str = Path(tts_audio).relative_to(Path("E:/project/srt-flow"))
                tts_str = str(tts_str).replace("\\", "/")
            except ValueError:
                tts_str = str(tts_audio)
            if os.name == 'nt' and "'" in tts_str:
                tts_str = self._get_short_path(tts_str)
            cmd.extend(["-i", tts_str])
            audio_input_index = 1  # TTS audio stream index
        
        # Video filter (subtitles)
        if filter_complex:
            cmd.extend(["-vf", filter_complex])
        
        # Audio processing based on mode
        if audio_mode == AudioMode.ORIGINAL:
            # Keep original audio
            cmd.extend(["-map", "0:v", "-map", "0:a"])
        elif audio_mode == AudioMode.TTS and tts_audio:
            # Replace with TTS audio, pad with silence if shorter than video
            cmd.extend([
                "-map", "0:v",
                "-filter_complex", "[1:a]apad[aout]",
                "-map", "[aout]",
                "-shortest"  # Stop encoding when video stream ends
            ])
        elif audio_mode == AudioMode.MIX and tts_audio:
            # Mix original + TTS audio, pad both to match video duration
            cmd.extend([
                "-map", "0:v",
                "-filter_complex", "[0:a]apad[a0];[1:a]apad[a1];[a0][a1]amix=inputs=2:duration=longest[aout]",
                "-map", "[aout]",
                "-shortest"  # Stop encoding when video stream ends
            ])
        else:
            # Fallback to original audio
            cmd.extend(["-map", "0:v", "-map", "0:a"])
        
        # Video encoding
        cmd.extend(self._get_video_encoder_args())
        
        # Audio encoding
        cmd.extend([
            "-c:a", self._config.audio_codec,
            "-b:a", self._config.audio_bitrate,
        ])
        
        # Output options - use relative path from project root
        try:
            output_str = Path(output_path).relative_to(Path("E:/project/srt-flow"))
            output_str = str(output_str).replace("\\", "/")
        except ValueError:
            output_str = str(output_path)
        if os.name == 'nt' and "'" in output_str:
            output_str = self._get_short_path(output_str)
        
        cmd.extend([
            "-y",  # Overwrite output
            output_str,
        ])
        
        return cmd

    def _build_subtitle_filter(
        self,
        video_path: Path,
        original_subtitle: Optional[Path],
        translated_subtitle: Optional[Path],
    ) -> Optional[str]:
        """Build subtitle filter string."""
        self._logger.info(f"=== _build_subtitle_filter called ===")
        self._logger.info(f"mode: {self._config.subtitle_mode}")
        self._logger.info(f"original_subtitle: {original_subtitle}")
        self._logger.info(f"translated_subtitle: {translated_subtitle}")
        self._logger.info(f"video_path: {video_path}")
        
        video_dir = video_path.parent
        filters = []
        
        # For subtitle paths, we need relative path from project root
        # Video path: data/downloads/.../video.mp4
        # Subtitle path: data/downloads/.../subtitle_translated.srt
        try:
            project_root = Path("E:/project/srt-flow")
            video_rel = Path(video_path).relative_to(project_root)
            video_parent_rel = str(video_rel.parent)
        except ValueError:
            video_parent_rel = "."
        
        mode = self._config.subtitle_mode
        
        self._logger.info(f"video_parent_rel: {video_parent_rel}")
        self._logger.info(f"=== Checking mode conditions ===")
        self._logger.info(f"ORIGINAL_ONLY check: {mode == SubtitleMode.ORIGINAL_ONLY} and {bool(original_subtitle)}")
        self._logger.info(f"TRANSLATED_ONLY check: {mode == SubtitleMode.TRANSLATED_ONLY} and {bool(translated_subtitle)}")
        
        if mode == SubtitleMode.ORIGINAL_ONLY and original_subtitle:
            self._logger.info("=== Taking ORIGINAL_ONLY branch ===")
            style = self._config.primary_style.to_ass_style_escaped()
            sub_path = self._escape_filter_path(original_subtitle, video_dir)
            filters.append(f"subtitles={sub_path}:force_style={style}")
            
        elif mode == SubtitleMode.TRANSLATED_ONLY and translated_subtitle:
            self._logger.info("=== Taking TRANSLATED_ONLY branch ===")
            style = self._config.primary_style.to_ass_style_escaped()
            sub_path = self._escape_filter_path(translated_subtitle, video_dir)
            filters.append(f"subtitles={sub_path}:force_style={style}")
            
        elif mode == SubtitleMode.DUAL:
            # First layer: translated subtitle (primary, bottom)
            if translated_subtitle:
                style = self._config.primary_style.to_ass_style_escaped()
                sub_path = self._escape_filter_path(translated_subtitle, video_dir)
                filters.append(f"subtitles={sub_path}:force_style={style}")
            
            # Second layer: original subtitle (secondary, above translated)
            if original_subtitle:
                style = self._config.secondary_style.to_ass_style_escaped()
                sub_path = self._escape_filter_path(original_subtitle, video_dir)
                filters.append(f"subtitles={sub_path}:force_style={style}")
        
        return ",".join(filters) if filters else None
    
    def _escape_filter_path(self, path: Path, video_dir: Path) -> str:
        """
        Escape path for FFmpeg subtitles filter.
        
        FFmpeg needs relative path from project root (same as video path).
        """
        path_str = str(path)
        
        self._logger.info(f"=== _escape_filter_path called ===")
        self._logger.info(f"Input path: {path_str}")
        self._logger.info(f"video_dir: {video_dir}")
        
        # Convert to relative path from project root (E:/project/srt-flow)
        try:
            project_root = Path("E:/project/srt-flow")
            rel_path = path.relative_to(project_root)
            path_str = str(rel_path).replace("\\", "/")
            self._logger.info(f"Relative path from project root: {path_str}")
        except ValueError:
            # If not under project root, try relative to video_dir
            try:
                rel_path = path.relative_to(video_dir)
                path_str = str(rel_path).replace("\\", "/")
                self._logger.info(f"Relative path from video_dir: {path_str}")
            except ValueError:
                # Last resort - convert WSL path
                if path_str.startswith("/mnt/"):
                    drive = path_str[5].upper()
                    rest = path_str[7:]
                    path_str = (drive + ":/" + rest).replace("\\", "/")
                elif path_str.startswith("/project/"):
                    path_str = ("E:/" + path_str[1:]).replace("\\", "/")
        
        final_path = f"=== FINAL SUBTITLE PATH: {path_str} ==="
        self._logger.info(final_path)
        
        return path_str
    
    def _get_short_path(self, path_str: str) -> str:
        """
        Get Windows short path (8.3 format) to avoid special characters.
        
        Args:
            path_str: Original path string
            
        Returns:
            Short path if successful, original path otherwise
        """
        try:
            import ctypes
            from ctypes import wintypes
            
            # Get short path name (8.3 format) which doesn't have special chars
            GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
            GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
            GetShortPathNameW.restype = wintypes.DWORD
            
            buffer_size = 512
            buffer = ctypes.create_unicode_buffer(buffer_size)
            ret = GetShortPathNameW(path_str, buffer, buffer_size)
            
            if ret and ret < buffer_size:
                short_path = buffer.value
                self._logger.debug(f"Short path: {path_str} -> {short_path}")
                return short_path
        except Exception as e:
            self._logger.warning(f"Failed to get short path for {path_str}: {e}")
        
        return path_str
    
    def _get_video_encoder_args(self) -> List[str]:
        """Get video encoder arguments."""
        args = []
        
        codec = self._config.video_codec
        hw = self._config.hardware_accel
        use_hw = self._config.use_hardware_encoder
        
        # Encoder selection
        if codec == VideoCodec.H264:
            if use_hw and hw == HardwareAccel.CUDA:
                args.extend(["-c:v", "h264_nvenc"])
            elif use_hw and hw == HardwareAccel.QSV:
                args.extend(["-c:v", "h264_qsv"])
            else:
                args.extend(["-c:v", "libx264"])
                args.extend(["-preset", self._config.video_preset])
                
        elif codec == VideoCodec.H265:
            if use_hw and hw == HardwareAccel.CUDA:
                args.extend(["-c:v", "hevc_nvenc"])
            elif use_hw and hw == HardwareAccel.QSV:
                args.extend(["-c:v", "hevc_qsv"])
            else:
                args.extend(["-c:v", "libx265"])
                args.extend(["-preset", self._config.video_preset])
                
        elif codec == VideoCodec.AV1:
            if use_hw and hw == HardwareAccel.CUDA:
                args.extend(["-c:v", "av1_nvenc"])
            else:
                args.extend(["-c:v", "libsvtav1"])
        
        # Quality setting
        if "nvenc" in args[-1] if args else False:
            args.extend(["-cq", str(self._config.video_crf)])
        else:
            args.extend(["-crf", str(self._config.video_crf)])
        
        return args


# ============================================================================
# Video Synthesizer Service
# ============================================================================

class SynthesizerService(BaseService):
    """
    Video synthesis service.
    
    Implements BaseService interface for worker integration.
    Uses FFmpeg for subtitle burning and video encoding.
    """
    
    def __init__(self, config: Optional[SynthesizerConfig] = None):
        """
        Initialize synthesizer service.
        
        Args:
            config: Synthesizer configuration
        """
        self._config = config or SynthesizerConfig()
        self._logger = get_logger("synthesizer")
        self._cmd_builder = FFmpegCommandBuilder(self._config)
        self._process: Optional[subprocess.Popen] = None
        self._current_task_id: Optional[str] = None
        self._cancelled = False
    
    async def execute(
        self,
        task: Task,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Dict:
        """Execute video synthesis task."""
        self._logger.info("=== SYNTHESIZER EXECUTE START ===")
        
        payload = task.payload or {}
        self._logger.info(f"Payload: {payload}")
        
        video_id = payload.get("video_id")
        video_path = payload.get("video_path")
        
        if not video_path:
            raise SynthesizerError("video_path is required")
        
        video_path = Path(video_path)
        if not video_path.exists():
            raise InputFileError(f"Video file not found: {video_path}")
        
        # Get subtitle paths
        original_sub = payload.get("original_subtitle_path")
        translated_sub = payload.get("translated_subtitle_path")
        tts_audio_path = payload.get("tts_audio_path")
        
        if original_sub:
            original_sub = Path(original_sub)
            if not original_sub.exists():
                original_sub = None
        
        if translated_sub:
            translated_sub = Path(translated_sub)
            if not translated_sub.exists():
                translated_sub = None
        
        if tts_audio_path:
            tts_audio_path = Path(tts_audio_path)
            if not tts_audio_path.exists():
                self._logger.warning(f"TTS audio not found: {tts_audio_path}")
                tts_audio_path = None
        
        # Validate subtitle availability based on mode
        mode = SubtitleMode(payload.get("subtitle_mode", self._config.subtitle_mode.value))
        audio_mode = AudioMode(payload.get("audio_mode", self._config.audio_mode.value))
        
        if mode == SubtitleMode.ORIGINAL_ONLY and not original_sub:
            raise InputFileError("Original subtitle required for original_only mode")
        if mode == SubtitleMode.TRANSLATED_ONLY and not translated_sub:
            raise InputFileError("Translated subtitle required for translated_only mode")
        if mode == SubtitleMode.DUAL and not (original_sub or translated_sub):
            raise InputFileError("At least one subtitle required for dual mode")
        
        # Apply custom styles if provided
        if payload.get("primary_subtitle_style"):
            self._apply_style(self._config.primary_style, payload["primary_subtitle_style"])
        if payload.get("secondary_subtitle_style"):
            self._apply_style(self._config.secondary_style, payload["secondary_subtitle_style"])
        
        # Apply encoder settings from payload
        video_encoder = payload.get("video_encoder")
        if video_encoder:
            # Map encoder string to config settings
            if video_encoder == "libx264":
                self._config.video_codec = VideoCodec.H264
                self._config.use_hardware_encoder = False
            elif video_encoder == "h264_nvenc":
                self._config.video_codec = VideoCodec.H264
                self._config.use_hardware_encoder = True
                self._config.hardware_accel = HardwareAccel.CUDA
            elif video_encoder == "libx265":
                self._config.video_codec = VideoCodec.H265
                self._config.use_hardware_encoder = False
            elif video_encoder == "hevc_nvenc":
                self._config.video_codec = VideoCodec.H265
                self._config.use_hardware_encoder = True
                self._config.hardware_accel = HardwareAccel.CUDA
        
        if payload.get("video_crf"):
            self._config.video_crf = payload["video_crf"]
        if payload.get("video_preset"):
            self._config.video_preset = payload["video_preset"]
        
        # Rebuild command builder with updated config
        self._cmd_builder = FFmpegCommandBuilder(self._config)
        
        # Update config mode
        self._config.subtitle_mode = mode
        self._config.audio_mode = audio_mode
        
        output_path = video_path.parent / "video_output.mp4"
        
        try:
            # Get video duration for progress calculation
            duration = await self._get_video_duration(video_path)
            
            progress_callback(0)
            self._logger.info(f"Starting synthesis: {video_path}")
            self._logger.info(f"Subtitle mode: {mode.value}, Audio mode: {audio_mode.value}, Duration: {duration}s")
            
            # Debug: log subtitle paths before building command
            self._logger.info(f"original_sub for cmd builder: {original_sub}")
            self._logger.info(f"translated_sub for cmd builder: {translated_sub}")
            
            # Build and execute FFmpeg command
            cmd = self._cmd_builder.build_synthesis_command(
                video_path, output_path, original_sub, translated_sub, tts_audio_path, audio_mode
            )
            
            self._logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            
            # Execute FFmpeg
            await self._execute_ffmpeg(cmd, duration, progress_callback)
            
            # Validate output
            if not output_path.exists():
                raise FFmpegError("Output file not created")
            
            file_size = output_path.stat().st_size
            if file_size == 0:
                raise FFmpegError("Output file is empty")
            
            progress_callback(100)
            
            return {
                "video_id": video_id,
                "output_path": str(output_path),
                "duration": duration,
                "file_size": file_size,
                "subtitle_mode": mode.value,
                "audio_mode": audio_mode.value,
                "hardware_accel": self._config.hardware_accel.value,
            }
            
        finally:
            self._current_task_id = None

    def _apply_style(self, style: SubtitleStyle, style_dict: Dict[str, Any]) -> None:
        """Apply style settings from dict to SubtitleStyle object."""
        for key, value in style_dict.items():
            if hasattr(style, key):
                if key == "position":
                    value = SubtitlePosition(value)
                setattr(style, key, value)
    
    async def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration using FFmpeg."""
        cmd = [
            self._config.ffmpeg_path,
            "-i", str(video_path),
            "-f", "null", "-"
        ]
        
        def run_ffprobe():
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return result.stderr.decode("utf-8", errors="replace")
        
        # Use thread pool to avoid Windows asyncio subprocess issues
        output = await asyncio.to_thread(run_ffprobe)
        
        # Parse duration
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
        if match:
            h, m, s, cs = map(int, match.groups())
            return h * 3600 + m * 60 + s + cs / 100
        
        return 0.0
    
    async def _execute_ffmpeg(
        self,
        cmd: List[str],
        total_duration: float,
        progress_callback: ProgressCallback,
    ) -> None:
        """Execute FFmpeg command with progress tracking."""
        import threading
        import queue as queue_module
        
        # Get video directory for working directory
        # Since we use relative paths from project root, cwd is E:/project/srt-flow
        try:
            video_idx = cmd.index("-i") + 1
            video_path_str = cmd[video_idx]
            self._logger.info(f"Video path from command: {video_path_str}")
            
            # For relative paths like data/downloads/..., the cwd is project root
            p = Path(video_path_str)
            if p.is_absolute():
                video_cwd = str(p.parent)
                self._logger.info(f"Absolute path, cwd: {video_cwd}")
            else:
                # Relative path - cwd should be project root
                video_cwd = "E:/project/srt-flow"
                self._logger.info(f"Relative path, using project root as cwd: {video_cwd}")
        except Exception as e:
            self._logger.warning(f"Failed to extract video directory: {e}")
            video_cwd = "E:/project/srt-flow"
        
        # Log full command for debugging
        cmd_str = ' '.join(cmd)
        self._logger.info(f"[DEBUG] FFmpeg command:\n{cmd_str}")
        self._logger.info(f"[DEBUG] Working directory: {video_cwd}")
        print(f"\n{'='*60}\n[FFMPEG CMD] {cmd_str}\n[FFMPEG CWD] {video_cwd}\n{'='*60}\n", flush=True)
        
        output_queue = queue_module.Queue()
        error_output = []  # Collect all stderr for error reporting
        
        def run_ffmpeg():
            """Run FFmpeg in a thread and put output lines to queue."""
            print(f"[FFMPEG] Starting process...", flush=True)
            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    errors="replace",
                    cwd=video_cwd,
                )
                self._process = process
                print(f"[FFMPEG] Process started, PID: {process.pid}", flush=True)
                
                # Read stderr line by line (FFmpeg outputs progress there)
                line_count = 0
                for line in process.stderr:
                    line = line.strip()
                    line_count += 1
                    error_output.append(line)
                    
                    # Print every line for debugging
                    if line:
                        print(f"[FFMPEG] {line}", flush=True)
                    
                    output_queue.put(("line", line))
                    if self._cancelled:
                        print(f"[FFMPEG] Cancelled, terminating...", flush=True)
                        process.terminate()
                        break
                
                print(f"[FFMPEG] Stderr reading done, total lines: {line_count}", flush=True)
                process.wait()
                print(f"[FFMPEG] Process exited with code: {process.returncode}", flush=True)
                output_queue.put(("done", process.returncode))
            except Exception as e:
                print(f"[FFMPEG] Exception in thread: {e}", flush=True)
                output_queue.put(("error", str(e)))
        
        def get_from_queue():
            """Helper to get from queue with timeout."""
            try:
                return output_queue.get(timeout=0.5)
            except queue_module.Empty:
                return None
        
        # Start FFmpeg in a thread
        thread = threading.Thread(target=run_ffmpeg, daemon=True)
        thread.start()
        print(f"[FFMPEG] Thread started, waiting for output...", flush=True)
        
        last_progress = 0
        wait_count = 0
        
        try:
            while True:
                if self._cancelled:
                    raise SynthesizerError("Synthesis cancelled")
                
                # Non-blocking queue read with timeout
                result = await asyncio.to_thread(get_from_queue)
                if result is None:
                    wait_count += 1
                    if wait_count % 20 == 0:  # Every 10 seconds
                        print(f"[FFMPEG] Still waiting... (waited {wait_count * 0.5}s)", flush=True)
                    continue
                
                wait_count = 0
                msg_type, data = result
                
                if msg_type == "error":
                    raise FFmpegError(f"Thread error: {data}")
                
                if msg_type == "done":
                    returncode = data
                    if returncode != 0:
                        # Include last few lines of output in error
                        last_output = '\n'.join(error_output[-20:])
                        raise FFmpegError(f"FFmpeg exited with code {returncode}\nOutput:\n{last_output}")
                    break
                
                elif msg_type == "line":
                    line_str = data
                    # Parse progress
                    progress_info = FFmpegProgressParser.parse_line(line_str)
                    if progress_info and total_duration > 0:
                        current_time = progress_info.get("current_time", 0)
                        progress = int((current_time / total_duration) * 100)
                        progress = min(progress, 99)  # Reserve 100 for completion
                        
                        if progress > last_progress:
                            last_progress = progress
                            progress_callback(progress)
                            print(f"[FFMPEG] Progress: {progress}%", flush=True)
            
            print(f"[FFMPEG] Waiting for thread to finish...", flush=True)
            thread.join(timeout=5.0)
            print(f"[FFMPEG] Done!", flush=True)
                
        finally:
            self._process = None
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel synthesis task."""
        if self._current_task_id != task_id:
            return False
        
        self._cancelled = True
        
        if self._process:
            self._process.terminate()
            try:
                # Wait for process to terminate
                await asyncio.to_thread(self._process.wait, timeout=5.0)
            except:
                self._process.kill()
        
        return True
    
    def can_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        error_str = str(error).lower()
        
        # Non-retryable errors
        non_retryable = [
            "file not found",
            "video file not found",
            "subtitle required",
            "encoder not available",
            "cancelled",
        ]
        if any(msg in error_str for msg in non_retryable):
            return False
        
        # Retryable errors
        retryable = [
            "output file is empty",
            "temporary",
        ]
        return any(msg in error_str for msg in retryable)
    
    # Utility methods
    def build_command(
        self,
        video_path: Path,
        output_path: Path,
        original_subtitle: Optional[Path] = None,
        translated_subtitle: Optional[Path] = None,
        tts_audio: Optional[Path] = None,
        audio_mode: AudioMode = AudioMode.ORIGINAL,
    ) -> List[str]:
        """Build FFmpeg command (for external use)."""
        return self._cmd_builder.build_synthesis_command(
            video_path, output_path, original_subtitle, translated_subtitle, tts_audio, audio_mode
        )
    
    def get_preset(self, name: str) -> Optional[StylePreset]:
        """Get a style preset by name."""
        return DEFAULT_PRESETS.get(name)
    
    def list_presets(self) -> List[str]:
        """List available preset names."""
        return list(DEFAULT_PRESETS.keys())
