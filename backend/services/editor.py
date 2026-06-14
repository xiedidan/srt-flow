"""
Editor Service Module.

Provides video editing functionality including preview, clipping,
multi-segment splitting, and subtitle synchronization using FFmpeg.
"""
import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.core.models import Task
from backend.core.logger import get_logger
from backend.workers.worker import BaseService, ProgressCallback


# ============================================================================
# Constants and Types
# ============================================================================

class ClipMode(str, Enum):
    """Video clipping modes."""
    FAST = "fast"      # No re-encoding, faster but may be inaccurate
    PRECISE = "precise"  # Re-encoding, accurate to frame


class OperationType(str, Enum):
    """Editor operation types."""
    CLIP = "clip"
    SPLIT = "split"


class PreviewQuality(str, Enum):
    """Preview quality options."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# Exceptions
# ============================================================================

class EditorError(Exception):
    """Base editor error."""
    pass


class VideoNotFoundError(EditorError):
    """Video file not found."""
    pass


class InvalidTimeRangeError(EditorError):
    """Invalid time range specified."""
    pass


class FFmpegError(EditorError):
    """FFmpeg execution error."""
    pass


class SubtitleError(EditorError):
    """Subtitle processing error."""
    pass


class DiskSpaceError(EditorError):
    """Insufficient disk space."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SplitPoint:
    """A split point definition."""
    time: float  # Time in seconds
    name: Optional[str] = None  # Optional segment name


@dataclass
class SegmentInfo:
    """Information about a video segment."""
    index: int
    start_time: float
    end_time: float
    duration: float
    output_path: str
    subtitle_path: Optional[str] = None


@dataclass
class ClipConfig:
    """Video clipping configuration."""
    mode: ClipMode = ClipMode.FAST
    video_codec: str = "copy"  # "copy" for fast, "libx264" for precise
    audio_codec: str = "copy"
    video_crf: int = 23
    output_name: Optional[str] = None


@dataclass
class SplitConfig:
    """Video splitting configuration."""
    mode: ClipMode = ClipMode.FAST
    video_codec: str = "copy"
    audio_codec: str = "copy"
    video_crf: int = 23
    name_pattern: str = "{name}_part{index:02d}"


@dataclass
class EditorConfig:
    """Editor service configuration."""
    default_clip_mode: ClipMode = ClipMode.FAST
    max_split_segments: int = 20
    min_segment_duration: int = 10
    auto_save_interval: int = 30
    preview_quality: PreviewQuality = PreviewQuality.MEDIUM
    ffmpeg_path: str = "ffmpeg"


# ============================================================================
# Subtitle Processor
# ============================================================================

class SubtitleProcessor:
    """Processes subtitles for video editing operations."""
    
    TIMESTAMP_PATTERN = re.compile(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    )
    
    def __init__(self):
        self._logger = get_logger("editor.subtitle")
    
    def parse_srt(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse SRT file into entries."""
        if not file_path.exists():
            return []
        
        content = file_path.read_text(encoding="utf-8")
        entries = []
        
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            lines = block.split('\n')
            if len(lines) < 3:
                continue
            
            try:
                index = int(lines[0].strip())
                match = self.TIMESTAMP_PATTERN.match(lines[1].strip())
                if not match:
                    continue
                
                sh, sm, ss, sms = map(int, match.groups()[:4])
                start = sh * 3600 + sm * 60 + ss + sms / 1000
                
                eh, em, es, ems = map(int, match.groups()[4:])
                end = eh * 3600 + em * 60 + es + ems / 1000
                
                text = '\n'.join(lines[2:]).strip()
                
                entries.append({
                    "index": index,
                    "start": start,
                    "end": end,
                    "text": text,
                })
            except (ValueError, IndexError):
                continue
        
        return entries
    
    def clip_subtitles(
        self,
        entries: List[Dict[str, Any]],
        start_time: float,
        end_time: float,
    ) -> List[Dict[str, Any]]:
        """
        Clip subtitles to match video clip range.
        
        Adjusts timestamps relative to new start time.
        """
        clipped = []
        new_index = 1
        
        for entry in entries:
            # Skip entries outside the range
            if entry["end"] <= start_time or entry["start"] >= end_time:
                continue
            
            # Adjust timestamps
            new_start = max(0, entry["start"] - start_time)
            new_end = min(end_time - start_time, entry["end"] - start_time)
            
            clipped.append({
                "index": new_index,
                "start": new_start,
                "end": new_end,
                "text": entry["text"],
            })
            new_index += 1
        
        return clipped

    
    def generate_srt(
        self,
        entries: List[Dict[str, Any]],
        output_path: Path,
    ) -> None:
        """Generate SRT file from entries."""
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(f"{entry['index']}\n")
                f.write(f"{self._format_time(entry['start'])} --> {self._format_time(entry['end'])}\n")
                f.write(f"{entry['text']}\n\n")
        
        self._logger.info(f"Generated SRT with {len(entries)} entries: {output_path}")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds to SRT timestamp format."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    def offset_subtitles(
        self,
        entries: List[Dict[str, Any]],
        offset: float,
    ) -> List[Dict[str, Any]]:
        """Apply time offset to all subtitle entries."""
        return [
            {
                **entry,
                "start": max(0, entry["start"] + offset),
                "end": max(0, entry["end"] + offset),
            }
            for entry in entries
        ]


# ============================================================================
# FFmpeg Progress Parser
# ============================================================================

class FFmpegProgressParser:
    """Parses FFmpeg output for progress information."""
    
    TIME_PATTERN = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})')
    SPEED_PATTERN = re.compile(r'speed=\s*([\d.]+)x')
    
    @classmethod
    def parse_line(cls, line: str) -> Optional[Dict[str, Any]]:
        """Parse FFmpeg progress line."""
        time_match = cls.TIME_PATTERN.search(line)
        if not time_match:
            return None
        
        h, m, s, cs = map(int, time_match.groups())
        current_time = h * 3600 + m * 60 + s + cs / 100
        
        result = {"current_time": current_time}
        
        speed_match = cls.SPEED_PATTERN.search(line)
        if speed_match:
            result["speed"] = float(speed_match.group(1))
        
        return result


# ============================================================================
# Video Clipper
# ============================================================================

class VideoClipper:
    """Handles video clipping operations."""
    
    def __init__(self, config: EditorConfig):
        self._config = config
        self._logger = get_logger("editor.clipper")
        self._subtitle_processor = SubtitleProcessor()
    
    def build_clip_command(
        self,
        input_path: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
        clip_config: ClipConfig,
    ) -> List[str]:
        """Build FFmpeg command for video clipping."""
        cmd = [self._config.ffmpeg_path]
        
        # Input seeking (before -i for fast mode)
        if clip_config.mode == ClipMode.FAST:
            cmd.extend(["-ss", str(start_time)])
        
        cmd.extend(["-i", str(input_path)])
        
        # Output seeking (after -i for precise mode)
        if clip_config.mode == ClipMode.PRECISE:
            cmd.extend(["-ss", str(start_time)])
        
        # Duration
        duration = end_time - start_time
        cmd.extend(["-t", str(duration)])
        
        # Video codec
        if clip_config.mode == ClipMode.FAST:
            cmd.extend(["-c:v", "copy"])
        else:
            cmd.extend([
                "-c:v", clip_config.video_codec or "libx264",
                "-crf", str(clip_config.video_crf),
            ])
        
        # Audio codec
        cmd.extend(["-c:a", clip_config.audio_codec or "copy"])
        
        # Output
        cmd.extend(["-y", str(output_path)])
        
        return cmd
    
    async def clip(
        self,
        input_path: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
        clip_config: ClipConfig,
        subtitle_paths: Optional[List[Path]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """
        Clip video to specified time range.
        
        Returns:
            Clip result with output paths
        """
        # Validate time range
        if start_time >= end_time:
            raise InvalidTimeRangeError(
                f"Start time ({start_time}) must be less than end time ({end_time})"
            )
        
        if start_time < 0:
            raise InvalidTimeRangeError("Start time cannot be negative")
        
        duration = end_time - start_time
        
        # Build and execute command
        cmd = self.build_clip_command(
            input_path, output_path, start_time, end_time, clip_config
        )
        
        self._logger.info(f"Clipping {input_path}: {start_time}s - {end_time}s")
        self._logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        await self._execute_ffmpeg(cmd, duration, progress_callback)
        
        # Process subtitles
        subtitle_outputs = []
        if subtitle_paths:
            for sub_path in subtitle_paths:
                if sub_path.exists():
                    output_sub = output_path.parent / f"{output_path.stem}_{sub_path.name}"
                    self._process_subtitle(sub_path, output_sub, start_time, end_time)
                    subtitle_outputs.append(str(output_sub))
        
        return {
            "output_path": str(output_path),
            "subtitle_paths": subtitle_outputs,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
        }

    
    async def _execute_ffmpeg(
        self,
        cmd: List[str],
        total_duration: float,
        progress_callback: Optional[ProgressCallback],
    ) -> None:
        """Execute FFmpeg command with progress tracking."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,  # Prevent interactive mode
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        last_progress = 0
        
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            
            line_str = line.decode("utf-8", errors="replace").strip()
            
            if progress_callback and total_duration > 0:
                progress_info = FFmpegProgressParser.parse_line(line_str)
                if progress_info:
                    current_time = progress_info.get("current_time", 0)
                    progress = int((current_time / total_duration) * 100)
                    progress = min(progress, 99)
                    
                    if progress > last_progress:
                        last_progress = progress
                        progress_callback(progress)
        
        await process.wait()
        
        if process.returncode != 0:
            raise FFmpegError(f"FFmpeg exited with code {process.returncode}")
    
    def _process_subtitle(
        self,
        input_path: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
    ) -> None:
        """Process subtitle file for clipped video."""
        entries = self._subtitle_processor.parse_srt(input_path)
        clipped = self._subtitle_processor.clip_subtitles(entries, start_time, end_time)
        self._subtitle_processor.generate_srt(clipped, output_path)


# ============================================================================
# Video Splitter
# ============================================================================

class VideoSplitter:
    """Handles video splitting operations."""
    
    def __init__(self, config: EditorConfig):
        self._config = config
        self._logger = get_logger("editor.splitter")
        self._subtitle_processor = SubtitleProcessor()
    
    def validate_split_points(
        self,
        split_points: List[SplitPoint],
        video_duration: float,
    ) -> None:
        """Validate split points."""
        if len(split_points) > self._config.max_split_segments - 1:
            raise InvalidTimeRangeError(
                f"Too many split points. Maximum: {self._config.max_split_segments - 1}"
            )
        
        # Sort by time
        sorted_points = sorted(split_points, key=lambda p: p.time)
        
        # Check each segment duration
        prev_time = 0.0
        for point in sorted_points:
            if point.time <= prev_time:
                raise InvalidTimeRangeError(
                    f"Split points must be in ascending order: {point.time} <= {prev_time}"
                )
            
            if point.time >= video_duration:
                raise InvalidTimeRangeError(
                    f"Split point {point.time} exceeds video duration {video_duration}"
                )
            
            segment_duration = point.time - prev_time
            if segment_duration < self._config.min_segment_duration:
                raise InvalidTimeRangeError(
                    f"Segment duration {segment_duration}s is less than minimum {self._config.min_segment_duration}s"
                )
            
            prev_time = point.time
        
        # Check last segment
        last_segment = video_duration - prev_time
        if last_segment < self._config.min_segment_duration:
            raise InvalidTimeRangeError(
                f"Last segment duration {last_segment}s is less than minimum {self._config.min_segment_duration}s"
            )
    
    def generate_segments(
        self,
        split_points: List[SplitPoint],
        video_duration: float,
        base_name: str,
        output_dir: Path,
        config: SplitConfig,
    ) -> List[SegmentInfo]:
        """Generate segment information from split points."""
        sorted_points = sorted(split_points, key=lambda p: p.time)
        segments = []
        
        prev_time = 0.0
        for i, point in enumerate(sorted_points):
            segment_name = config.name_pattern.format(
                name=base_name,
                index=i + 1,
            )
            output_path = output_dir / f"{segment_name}.mp4"
            
            segments.append(SegmentInfo(
                index=i + 1,
                start_time=prev_time,
                end_time=point.time,
                duration=point.time - prev_time,
                output_path=str(output_path),
            ))
            
            prev_time = point.time
        
        # Last segment
        segment_name = config.name_pattern.format(
            name=base_name,
            index=len(sorted_points) + 1,
        )
        output_path = output_dir / f"{segment_name}.mp4"
        
        segments.append(SegmentInfo(
            index=len(sorted_points) + 1,
            start_time=prev_time,
            end_time=video_duration,
            duration=video_duration - prev_time,
            output_path=str(output_path),
        ))
        
        return segments

    
    @staticmethod
    def generate_equal_split_points(
        video_duration: float,
        num_segments: int,
    ) -> List[SplitPoint]:
        """Generate split points for equal-duration segments."""
        if num_segments < 2:
            return []
        
        segment_duration = video_duration / num_segments
        points = []
        
        for i in range(1, num_segments):
            points.append(SplitPoint(time=segment_duration * i))
        
        return points
    
    @staticmethod
    def generate_duration_split_points(
        video_duration: float,
        segment_duration: float,
    ) -> List[SplitPoint]:
        """Generate split points for fixed-duration segments."""
        if segment_duration >= video_duration:
            return []
        
        points = []
        current_time = segment_duration
        
        while current_time < video_duration:
            points.append(SplitPoint(time=current_time))
            current_time += segment_duration
        
        return points
    
    async def split(
        self,
        input_path: Path,
        split_points: List[SplitPoint],
        video_duration: float,
        output_dir: Path,
        split_config: SplitConfig,
        subtitle_paths: Optional[List[Path]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[SegmentInfo]:
        """
        Split video into multiple segments.
        
        Returns:
            List of segment information
        """
        # Validate
        self.validate_split_points(split_points, video_duration)
        
        # Generate segment info
        base_name = input_path.stem
        segments = self.generate_segments(
            split_points, video_duration, base_name, output_dir, split_config
        )
        
        total_segments = len(segments)
        self._logger.info(f"Splitting {input_path} into {total_segments} segments")
        
        # Process each segment
        for i, segment in enumerate(segments):
            if progress_callback:
                base_progress = int((i / total_segments) * 100)
                progress_callback(base_progress)
            
            # Build FFmpeg command
            cmd = self._build_segment_command(
                input_path,
                Path(segment.output_path),
                segment.start_time,
                segment.end_time,
                split_config,
            )
            
            self._logger.info(f"Processing segment {i + 1}/{total_segments}")
            
            # Execute
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,  # Prevent interactive mode
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await process.wait()
            
            if process.returncode != 0:
                raise FFmpegError(f"Failed to create segment {i + 1}")
            
            # Process subtitles for this segment
            if subtitle_paths:
                for sub_path in subtitle_paths:
                    if sub_path.exists():
                        output_sub = Path(segment.output_path).with_suffix(f".{sub_path.suffix}")
                        output_sub = output_dir / f"{Path(segment.output_path).stem}_{sub_path.name}"
                        self._process_subtitle(
                            sub_path, output_sub,
                            segment.start_time, segment.end_time
                        )
                        segment.subtitle_path = str(output_sub)
        
        if progress_callback:
            progress_callback(100)
        
        return segments

    
    def _build_segment_command(
        self,
        input_path: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
        config: SplitConfig,
    ) -> List[str]:
        """Build FFmpeg command for a single segment."""
        cmd = [self._config.ffmpeg_path]
        
        # Fast mode: seek before input
        if config.mode == ClipMode.FAST:
            cmd.extend(["-ss", str(start_time)])
        
        cmd.extend(["-i", str(input_path)])
        
        # Precise mode: seek after input
        if config.mode == ClipMode.PRECISE:
            cmd.extend(["-ss", str(start_time)])
        
        # Duration
        duration = end_time - start_time
        cmd.extend(["-t", str(duration)])
        
        # Codecs
        if config.mode == ClipMode.FAST:
            cmd.extend(["-c:v", "copy", "-c:a", "copy"])
        else:
            cmd.extend([
                "-c:v", config.video_codec or "libx264",
                "-crf", str(config.video_crf),
                "-c:a", config.audio_codec or "aac",
            ])
        
        cmd.extend(["-y", str(output_path)])
        
        return cmd
    
    def _process_subtitle(
        self,
        input_path: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
    ) -> None:
        """Process subtitle for a segment."""
        entries = self._subtitle_processor.parse_srt(input_path)
        clipped = self._subtitle_processor.clip_subtitles(entries, start_time, end_time)
        self._subtitle_processor.generate_srt(clipped, output_path)


# ============================================================================
# Editor Service
# ============================================================================

class EditorService(BaseService):
    """
    Video editor service.
    
    Implements BaseService interface for worker integration.
    Provides video clipping, splitting, and subtitle processing.
    """
    
    def __init__(self, config: Optional[EditorConfig] = None):
        """
        Initialize editor service.
        
        Args:
            config: Editor configuration
        """
        self._config = config or EditorConfig()
        self._logger = get_logger("editor")
        self._clipper = VideoClipper(self._config)
        self._splitter = VideoSplitter(self._config)
        self._subtitle_processor = SubtitleProcessor()
        self._current_task_id: Optional[str] = None
        self._cancelled = False
        self._process: Optional[asyncio.subprocess.Process] = None
    
    async def execute(
        self,
        task: Task,
        progress_callback: ProgressCallback,
        payload_callback=None,
    ) -> Dict[str, Any]:
        """
        Execute editor task.
        
        Args:
            task: Editor task
            progress_callback: Progress callback
            payload_callback: Optional callback to update task payload (unused)
            
        Returns:
            Edit result
        """
        self._current_task_id = task.id
        self._cancelled = False
        payload = task.payload or {}
        
        video_id = payload.get("video_id")
        video_path = payload.get("video_path")
        operation = payload.get("operation", OperationType.CLIP.value)
        
        if not video_path:
            raise EditorError("video_path is required")
        
        video_path = Path(video_path)
        if not video_path.exists():
            raise VideoNotFoundError(f"Video file not found: {video_path}")
        
        # Get video duration
        duration = await self._get_video_duration(video_path)
        
        # Get subtitle paths
        subtitle_paths = []
        for sub_key in ["original_subtitle_path", "translated_subtitle_path"]:
            if payload.get(sub_key):
                sub_path = Path(payload[sub_key])
                if sub_path.exists():
                    subtitle_paths.append(sub_path)
        
        progress_callback(0)
        
        try:
            if operation == OperationType.CLIP.value:
                result = await self._execute_clip(
                    video_path, duration, subtitle_paths, payload, progress_callback
                )
            elif operation == OperationType.SPLIT.value:
                result = await self._execute_split(
                    video_path, duration, subtitle_paths, payload, progress_callback
                )
            else:
                raise EditorError(f"Unknown operation: {operation}")
            
            result["video_id"] = video_id
            result["operation"] = operation
            
            progress_callback(100)
            return result
            
        finally:
            self._current_task_id = None

    
    async def _execute_clip(
        self,
        video_path: Path,
        duration: float,
        subtitle_paths: List[Path],
        payload: Dict[str, Any],
        progress_callback: ProgressCallback,
    ) -> Dict[str, Any]:
        """Execute clip operation."""
        start_time = payload.get("start_time", 0)
        end_time = payload.get("end_time", duration)
        
        # Build clip config
        clip_config = ClipConfig(
            mode=ClipMode(payload.get("clip_mode", self._config.default_clip_mode.value)),
            output_name=payload.get("output_name"),
        )
        
        # Determine output path
        if clip_config.output_name:
            output_path = video_path.parent / f"{clip_config.output_name}.mp4"
        else:
            output_path = video_path.parent / f"{video_path.stem}_clip.mp4"
        
        self._logger.info(f"Clipping video: {start_time}s - {end_time}s")
        
        result = await self._clipper.clip(
            video_path,
            output_path,
            start_time,
            end_time,
            clip_config,
            subtitle_paths,
            progress_callback,
        )
        
        return {
            "output_files": [result["output_path"]],
            "subtitle_files": result["subtitle_paths"],
            "clip_info": {
                "start_time": start_time,
                "end_time": end_time,
                "duration": result["duration"],
            },
        }
    
    async def _execute_split(
        self,
        video_path: Path,
        duration: float,
        subtitle_paths: List[Path],
        payload: Dict[str, Any],
        progress_callback: ProgressCallback,
    ) -> Dict[str, Any]:
        """Execute split operation."""
        # Get split points
        split_points_data = payload.get("split_points", [])
        
        # Support different split modes
        if payload.get("equal_segments"):
            # Equal segment split
            num_segments = payload["equal_segments"]
            split_points = VideoSplitter.generate_equal_split_points(duration, num_segments)
        elif payload.get("segment_duration"):
            # Fixed duration split
            seg_duration = payload["segment_duration"]
            split_points = VideoSplitter.generate_duration_split_points(duration, seg_duration)
        else:
            # Manual split points
            split_points = [
                SplitPoint(time=p.get("time", p), name=p.get("name") if isinstance(p, dict) else None)
                for p in split_points_data
            ]
        
        if not split_points:
            raise EditorError("No split points specified")
        
        # Build split config
        split_config = SplitConfig(
            mode=ClipMode(payload.get("clip_mode", self._config.default_clip_mode.value)),
            name_pattern=payload.get("name_pattern", "{name}_part{index:02d}"),
        )
        
        output_dir = video_path.parent
        
        self._logger.info(f"Splitting video into {len(split_points) + 1} segments")
        
        segments = await self._splitter.split(
            video_path,
            split_points,
            duration,
            output_dir,
            split_config,
            subtitle_paths,
            progress_callback,
        )
        
        return {
            "output_files": [s.output_path for s in segments],
            "subtitle_files": [s.subtitle_path for s in segments if s.subtitle_path],
            "segments_info": [
                {
                    "index": s.index,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.duration,
                    "output_path": s.output_path,
                    "subtitle_path": s.subtitle_path,
                }
                for s in segments
            ],
        }

    
    async def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration using FFmpeg."""
        cmd = [
            self._config.ffmpeg_path,
            "-i", str(video_path),
            "-f", "null", "-"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,  # Prevent interactive mode
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        _, stderr = await process.communicate()
        output = stderr.decode("utf-8", errors="replace")
        
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
        if match:
            h, m, s, cs = map(int, match.groups())
            return h * 3600 + m * 60 + s + cs / 100
        
        return 0.0
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel editor task."""
        if self._current_task_id != task_id:
            return False
        
        self._cancelled = True
        
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
        
        return True
    
    def can_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        error_str = str(error).lower()
        
        # Non-retryable errors
        non_retryable = [
            "file not found",
            "video file not found",
            "invalid time range",
            "too many split points",
            "cancelled",
            "disk space",
        ]
        if any(msg in error_str for msg in non_retryable):
            return False
        
        # Retryable errors
        retryable = [
            "temporary",
            "resource",
        ]
        return any(msg in error_str for msg in retryable)
    
    # Utility methods for external use
    async def clip_video(
        self,
        video_path: Path,
        start_time: float,
        end_time: float,
        output_path: Optional[Path] = None,
        config: Optional[ClipConfig] = None,
    ) -> Dict[str, Any]:
        """Clip video (standalone method)."""
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}_clip.mp4"
        
        clip_config = config or ClipConfig(mode=self._config.default_clip_mode)
        
        return await self._clipper.clip(
            video_path, output_path, start_time, end_time, clip_config
        )
    
    async def split_video(
        self,
        video_path: Path,
        split_points: List[SplitPoint],
        output_dir: Optional[Path] = None,
        config: Optional[SplitConfig] = None,
    ) -> List[SegmentInfo]:
        """Split video (standalone method)."""
        duration = await self._get_video_duration(video_path)
        
        if output_dir is None:
            output_dir = video_path.parent
        
        split_config = config or SplitConfig(mode=self._config.default_clip_mode)
        
        return await self._splitter.split(
            video_path, split_points, duration, output_dir, split_config
        )
    
    def get_preview_url(self, video_id: str, video_path: Path) -> str:
        """Get preview URL for video (to be implemented with API layer)."""
        return f"/api/v1/videos/{video_id}/preview"
    
    def save_subtitle(
        self,
        entries: List[Dict[str, Any]],
        output_path: Path,
    ) -> None:
        """Save edited subtitle."""
        self._subtitle_processor.generate_srt(entries, output_path)
    
    def parse_subtitle(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse subtitle file."""
        return self._subtitle_processor.parse_srt(file_path)
    
    def offset_subtitle(
        self,
        entries: List[Dict[str, Any]],
        offset: float,
    ) -> List[Dict[str, Any]]:
        """Apply time offset to subtitle entries."""
        return self._subtitle_processor.offset_subtitles(entries, offset)
