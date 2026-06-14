"""
Download Service Module.

Provides video download functionality using yt-dlp and BiliDown tools.
Supports YouTube and Bilibili platforms with progress tracking.
"""
import asyncio
import json
import os
import re
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from backend.core.models import Task, Video, VideoFile, VideoSource, FileType
from backend.core.config import DownloadConfig
from backend.core.logger import get_logger
from backend.workers.worker import BaseService, ProgressCallback


# ============================================================================
# Constants and Types
# ============================================================================

class DownloadChannel(str, Enum):
    """Download channel options."""
    YT_DLP = "yt-dlp"
    BILIDOWN = "bilidown"


class VideoQuality(str, Enum):
    """Video quality options."""
    BEST = "best"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"
    AUDIO_ONLY = "audio_only"


# Platform detection patterns
URL_PATTERNS = {
    VideoSource.YOUTUBE: [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ],
    VideoSource.BILIBILI: [
        r'(?:https?://)?(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)',
        r'(?:https?://)?b23\.tv/([a-zA-Z0-9]+)',
        r'(?:https?://)?(?:www\.)?bilibili\.com/video/(av\d+)',
    ],
}

# Channel compatibility
CHANNEL_PLATFORMS = {
    DownloadChannel.YT_DLP: [VideoSource.YOUTUBE, VideoSource.BILIBILI, VideoSource.LOCAL],
    DownloadChannel.BILIDOWN: [VideoSource.BILIBILI],
}


# ============================================================================
# Exceptions
# ============================================================================

class DownloadError(Exception):
    """Base download error."""
    pass


class UnsupportedURLError(DownloadError):
    """URL not supported."""
    pass


class ChannelIncompatibleError(DownloadError):
    """Channel not compatible with platform."""
    pass


class DuplicateVideoError(DownloadError):
    """Video already exists."""
    def __init__(self, video_id: str, message: str = "Video already exists"):
        self.video_id = video_id
        super().__init__(message)


class DownloadFailedError(DownloadError):
    """Download failed."""
    pass


# ============================================================================
# Configuration
# ============================================================================

class YtDlpDownloaderConfig:
    """yt-dlp downloader configuration."""
    
    def __init__(
        self,
        preferred_quality: VideoQuality = VideoQuality.BEST,
        download_subtitles: bool = True,
        download_thumbnail: bool = True,
        proxy_url: Optional[str] = None,
        cookies_browser: Optional[str] = None,
        max_filesize: Optional[str] = None,
        nodejs_path: Optional[str] = None,
        yt_dlp_path: str = "yt-dlp",
        bilidown_path: Optional[str] = None,
        download_dir: str = "data/downloads",
    ):
        self.preferred_quality = preferred_quality
        self.download_subtitles = download_subtitles
        self.download_thumbnail = download_thumbnail
        self.proxy_url = proxy_url
        self.cookies_browser = cookies_browser
        self.max_filesize = max_filesize
        self.nodejs_path = nodejs_path
        self.yt_dlp_path = yt_dlp_path
        self.bilidown_path = bilidown_path
        self.download_dir = download_dir



# ============================================================================
# URL Parser
# ============================================================================

class URLParser:
    """Parses video URLs to extract platform and video ID."""
    
    @staticmethod
    def parse(url: str) -> Tuple[VideoSource, str]:
        """
        Parse URL to extract platform and video ID.
        
        Args:
            url: Video URL
            
        Returns:
            Tuple of (platform, video_id)
            
        Raises:
            UnsupportedURLError: If URL is not supported
        """
        url = url.strip()
        
        for platform, patterns in URL_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return platform, match.group(1)
        
        raise UnsupportedURLError(f"Unsupported URL: {url}")
    
    @staticmethod
    def validate_channel(channel: DownloadChannel, platform: VideoSource) -> bool:
        """
        Validate channel compatibility with platform.
        
        Args:
            channel: Download channel
            platform: Video platform
            
        Returns:
            True if compatible
        """
        return platform in CHANNEL_PLATFORMS.get(channel, [])


# ============================================================================
# Progress Parser
# ============================================================================

class ProgressParser:
    """Parses download progress from tool output."""
    
    # yt-dlp progress pattern: [download]  45.2% of 125.00MiB at 2.50MiB/s ETA 00:25
    YT_DLP_PATTERN = re.compile(
        r'\[download\]\s+(\d+\.?\d*)%\s+of\s+[\d.]+\w+\s+at\s+([\d.]+\w+/s)\s+ETA\s+(\d+:\d+)'
    )
    
    # Alternative pattern for simpler output
    YT_DLP_SIMPLE_PATTERN = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
    
    # Pattern to detect file destination: [download] Destination: video.f137.mp4
    YT_DLP_DESTINATION_PATTERN = re.compile(r'\[download\]\s+Destination:\s+(.+)')
    
    # Pattern to detect download completion: [download] 100% of 125.00MiB
    YT_DLP_COMPLETE_PATTERN = re.compile(r'\[download\]\s+100%\s+of')
    
    # Pattern to detect already downloaded: [download] video.mp4 has already been downloaded
    YT_DLP_ALREADY_DOWNLOADED_PATTERN = re.compile(r'\[download\]\s+(.+)\s+has already been downloaded')
    
    # Pattern to detect merging: [Merger] Merging formats into
    YT_DLP_MERGER_PATTERN = re.compile(r'\[Merger\]\s+Merging formats into')
    
    @classmethod
    def parse_yt_dlp(cls, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse yt-dlp progress line.
        
        Args:
            line: Output line from yt-dlp
            
        Returns:
            Progress info dict or None
        """
        # Check for destination (new file starting)
        match = cls.YT_DLP_DESTINATION_PATTERN.search(line)
        if match:
            return {
                "type": "new_file",
                "filename": match.group(1),
            }
        
        # Check for already downloaded
        match = cls.YT_DLP_ALREADY_DOWNLOADED_PATTERN.search(line)
        if match:
            return {
                "type": "file_complete",
                "filename": match.group(1),
            }
        
        # Check for merger (indicates all downloads complete, merging)
        if cls.YT_DLP_MERGER_PATTERN.search(line):
            return {
                "type": "merging",
            }
        
        # Check for progress with details
        match = cls.YT_DLP_PATTERN.search(line)
        if match:
            return {
                "type": "progress",
                "progress": int(float(match.group(1))),
                "speed": match.group(2),
                "eta": match.group(3),
            }
        
        # Try simple pattern
        match = cls.YT_DLP_SIMPLE_PATTERN.search(line)
        if match:
            progress = int(float(match.group(1)))
            return {
                "type": "progress" if progress < 100 else "file_complete",
                "progress": progress,
            }
        
        return None


# ============================================================================
# Directory Manager
# ============================================================================

class DirectoryManager:
    """Manages video download directories."""
    
    def __init__(self, base_dir: str = "data/downloads"):
        self._base_dir = Path(base_dir)
    
    def create_video_directory(self, video_id: str, title: str) -> Path:
        """
        Create directory for video.
        
        Args:
            video_id: Video UUID
            title: Video title
            
        Returns:
            Path to created directory
        """
        safe_title = self._make_safe_title(title)
        dir_name = f"{video_id}_{safe_title}"
        dir_path = self._base_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    def _make_safe_title(self, title: str, max_length: int = 50) -> str:
        """Convert title to safe directory name."""
        # Replace unsafe characters (including comma for FFmpeg filter compatibility)
        safe = re.sub(r'[<>:"/\\|?*,]', '_', title)
        # Replace multiple spaces/underscores
        safe = re.sub(r'[\s_]+', '_', safe)
        # Remove leading/trailing underscores
        safe = safe.strip('_')
        # Truncate
        if len(safe) > max_length:
            safe = safe[:max_length].rstrip('_')
        return safe or "untitled"



# ============================================================================
# yt-dlp Downloader
# ============================================================================

class YtDlpDownloader:
    """yt-dlp based video downloader."""
    
    def __init__(self, config: Union['DownloadConfig', 'YtDlpDownloaderConfig']):
        self._config = config
        self._logger = get_logger("download.yt_dlp")
        self._process: Optional[asyncio.subprocess.Process] = None
    
    async def fetch_metadata(self, url: str) -> Dict[str, Any]:
        """
        Fetch video metadata without downloading.
        
        Uses yt-dlp --skip-download to quickly get video info.
        
        Args:
            url: Video URL
            
        Returns:
            Metadata dict with title, thumbnail_url, duration, channel_name, etc.
        """
        import subprocess
        import tempfile
        
        cmd = [self._config.yt_dlp_path]
        
        # Skip download, only get info
        cmd.append("--skip-download")
        
        # Write info JSON to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            info_path = f.name
        
        cmd.extend(["--write-info-json", "-o", info_path.replace('.json', '')])
        
        # Proxy
        if self._config.proxy_url:
            cmd.extend(["--proxy", self._config.proxy_url])
        
        # Cookies from browser
        if self._config.cookies_browser and self._config.cookies_browser != "none":
            cmd.extend(["--cookies-from-browser", self._config.cookies_browser])
        
        # No warnings
        cmd.append("--no-warnings")
        
        # URL
        cmd.append(url)
        
        self._logger.info(f"Fetching metadata: {' '.join(cmd)}")
        
        loop = asyncio.get_event_loop()
        
        def run_fetch():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,  # 60s timeout for metadata fetch
                )
                return result.returncode
            except subprocess.TimeoutExpired:
                self._logger.warning("Metadata fetch timed out")
                return -1
            except Exception as e:
                self._logger.error(f"Metadata fetch error: {e}")
                return -1
        
        try:
            returncode = await loop.run_in_executor(None, run_fetch)
            
            # Read info JSON
            info_json_path = Path(info_path.replace('.json', '.info.json'))
            if info_json_path.exists():
                with open(info_json_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                
                # Clean up temp file
                try:
                    info_json_path.unlink()
                except:
                    pass
                
                return {
                    "title": info.get("title", "Unknown"),
                    "thumbnail_url": info.get("thumbnail"),
                    "duration": info.get("duration"),
                    "channel_name": info.get("uploader") or info.get("channel"),
                    "channel_id": info.get("uploader_id") or info.get("channel_id"),
                    "description": info.get("description"),
                    "upload_date": info.get("upload_date"),
                }
            else:
                self._logger.warning(f"Info JSON not found at {info_json_path}")
                return {}
                
        except Exception as e:
            self._logger.error(f"Failed to fetch metadata: {e}")
            return {}
    
    def _build_command(
        self,
        url: str,
        output_dir: Path,
        quality: VideoQuality,
        force_h264: bool = False,
    ) -> List[str]:
        """Build yt-dlp command."""
        cmd = [self._config.yt_dlp_path]
        
        # Output template
        output_template = str(output_dir / "video.%(ext)s")
        cmd.extend(["-o", output_template])
        
        # Quality/format selection with optional H264 codec filter
        # H264 is required for browser video preview compatibility (HEVC not supported)
        # Note: Some YouTube videos may not have H264 formats available, so we provide fallback
        
        if quality == VideoQuality.AUDIO_ONLY:
            cmd.extend(["-f", "bestaudio/best", "-x"])
        elif quality == VideoQuality.BEST:
            if force_h264:
                # Prefer H264, but allow fallback to any format if H264 not available
                cmd.extend(["-f", "bestvideo[vcodec~='^(h264|avc)']+bestaudio/bestvideo+bestaudio/best"])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])
        else:
            # Map quality to format
            height = quality.value.replace("p", "")
            if force_h264:
                # Prefer H264 with height limit, fallback to non-H264 with height limit, then any format
                cmd.extend(["-f", f"bestvideo[height<={height}][vcodec~='^(h264|avc)']+bestaudio/bestvideo[height<={height}]+bestaudio/bestvideo+bestaudio/best"])
            else:
                # Prefer height-limited format, fallback to best available
                cmd.extend(["-f", f"bestvideo[height<={height}]+bestaudio/bestvideo+bestaudio/best"])
        
        # Merge to mp4
        cmd.extend(["--merge-output-format", "mp4"])
        
        # Write metadata
        cmd.append("--write-info-json")
        
        # Thumbnail
        if self._config.download_thumbnail:
            cmd.append("--write-thumbnail")
        
        # Subtitles
        if self._config.download_subtitles:
            cmd.extend(["--write-subs", "--sub-langs", "all"])
        
        # Proxy
        if self._config.proxy_url:
            cmd.extend(["--proxy", self._config.proxy_url])
        
        # Cookies from browser (Firefox recommended - doesn't lock database)
        if self._config.cookies_browser and self._config.cookies_browser != "none":
            cmd.extend(["--cookies-from-browser", self._config.cookies_browser])
            self._logger.info(f"Using cookies from browser: {self._config.cookies_browser}")
        
        # Max filesize
        if self._config.max_filesize:
            cmd.extend(["--max-filesize", self._config.max_filesize])
        
        # YouTube n-parameter challenge solving
        # Specify Node.js runtime and enable remote challenge solver if Node.js path is configured
        nodejs_path = getattr(self._config, 'nodejs_path', None)
        if nodejs_path:
            cmd.extend(["--js-runtimes", f"node:{nodejs_path}"])
            cmd.extend(["--remote-components", "ejs:github"])
            self._logger.info(f"Using Node.js for YouTube challenge solving: {nodejs_path}")
        
        # Progress output
        cmd.append("--newline")
        
        # Verbose output for debugging
        cmd.append("--verbose")
        
        # URL
        cmd.append(url)
        
        return cmd
    
    async def download(
        self,
        url: str,
        output_dir: Path,
        quality: VideoQuality,
        progress_callback: Optional[Callable[[int], None]] = None,
        force_h264: bool = False,
    ) -> Dict[str, Any]:
        """
        Download video using yt-dlp.
        
        Args:
            url: Video URL
            output_dir: Output directory
            quality: Video quality
            progress_callback: Progress callback
            force_h264: Force H264 codec for browser compatibility
            
        Returns:
            Download result with file paths
        """
        result = await self._run_download(url, output_dir, quality, progress_callback, force_h264)
        
        if result.get("error"):
            raise DownloadFailedError(result["error"])
        
        return result.get("files", {})
    
    async def _run_download(
        self,
        url: str,
        output_dir: Path,
        quality: VideoQuality,
        progress_callback: Optional[Callable[[int], None]],
        force_h264: bool = False,
    ) -> Dict[str, Any]:
        """
        Run yt-dlp download process.
        
        Tracks multi-file download progress to provide continuous progress updates.
        Progress is calculated as: (completed_files + current_file_progress/100) / total_files * 90
        The final 10% is reserved for merging.
        
        Returns dict with either 'files' on success, or 'error' on failure.
        """
        import subprocess
        
        cmd = self._build_command(url, output_dir, quality, force_h264)
        self._logger.info(f"Running: {' '.join(cmd)}")
        
        loop = asyncio.get_event_loop()
        error_lines = []
        
        def run_download():
            import os
            
            # Ensure Node.js is in PATH for yt-dlp's n-parameter challenge solving
            env = os.environ.copy()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            
            # Multi-file progress tracking
            # yt-dlp typically downloads: video stream, audio stream, then merges
            # We estimate 2-3 files for most downloads
            completed_files = 0
            current_file_progress = 0
            current_filename = None
            estimated_total_files = 2  # Will be updated as we see more files
            is_merging = False
            last_reported_progress = 0
            line_count = 0
            
            def calculate_overall_progress():
                """Calculate overall progress across all files."""
                if is_merging:
                    # Merging phase: 90-100%
                    return 95
                
                # Download phase: 0-90%
                # Each file contributes equally to the 90%
                file_weight = 90.0 / max(estimated_total_files, 1)
                progress = (completed_files * file_weight) + (current_file_progress / 100.0 * file_weight)
                return int(min(progress, 90))
            
            for line in process.stdout:
                line_str = line.strip()
                if line_str:
                    line_count += 1
                    # Log all output at info level for debugging
                    self._logger.info(f"[yt-dlp] {line_str}")
                    
                    # Capture error messages
                    if "ERROR:" in line_str or "error:" in line_str.lower():
                        error_lines.append(line_str)
                    
                    # Parse progress
                    if progress_callback:
                        progress_info = ProgressParser.parse_yt_dlp(line_str)
                        if progress_info:
                            info_type = progress_info.get("type")
                            
                            if info_type == "new_file":
                                # New file starting
                                if current_filename is not None:
                                    # Previous file completed
                                    completed_files += 1
                                current_filename = progress_info.get("filename")
                                current_file_progress = 0
                                # Update estimate if we see more files
                                if completed_files + 1 > estimated_total_files:
                                    estimated_total_files = completed_files + 1
                                self._logger.info(f"[yt-dlp] Starting file {completed_files + 1}: {current_filename}")
                                
                            elif info_type == "progress":
                                # File download progress
                                current_file_progress = progress_info.get("progress", 0)
                                
                            elif info_type == "file_complete":
                                # File completed
                                current_file_progress = 100
                                completed_files += 1
                                current_filename = None
                                self._logger.info(f"[yt-dlp] File completed, total: {completed_files}")
                                
                            elif info_type == "merging":
                                # Merging phase
                                is_merging = True
                                self._logger.info("[yt-dlp] Merging files...")
                            
                            # Calculate and report overall progress
                            overall_progress = calculate_overall_progress()
                            if overall_progress > last_reported_progress:
                                last_reported_progress = overall_progress
                                try:
                                    progress_callback(overall_progress)
                                except Exception:
                                    pass
            
            self._logger.info(f"[yt-dlp] Process finished, total lines: {line_count}, files: {completed_files}")
            process.wait()
            return process.returncode
        
        try:
            returncode = await loop.run_in_executor(None, run_download)
            
            if returncode != 0:
                error_detail = "; ".join(error_lines[-3:]) if error_lines else "Unknown error"
                return {"error": f"yt-dlp exited with code {returncode}: {error_detail}"}
            
            # Convert any .webp thumbnails to .png for broader compatibility
            self._convert_webp_to_png(output_dir)
            return {"files": self._collect_files(output_dir)}
            
        finally:
            self._process = None
    
    async def cancel(self) -> bool:
        """Cancel ongoing download."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            return True
        return False
    
    def _convert_webp_to_png(self, directory: Path) -> None:
        """
        Convert all .webp images in directory to .png using ffmpeg.
        Removes original .webp files after successful conversion.
        """
        import subprocess

        webp_files = list(directory.rglob("*.webp"))
        if not webp_files:
            return

        for webp_file in webp_files:
            png_file = webp_file.with_suffix(".png")
            try:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", str(webp_file), str(png_file)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    webp_file.unlink()
                    self._logger.info(f"Converted {webp_file.name} -> {png_file.name}")
                else:
                    self._logger.warning(
                        f"Failed to convert {webp_file.name}: {result.stderr.strip()}"
                    )
            except Exception as e:
                self._logger.error(f"Error converting {webp_file}: {e}")

    def _collect_files(self, output_dir: Path) -> Dict[str, str]:
        """Collect downloaded files."""
        files = {}
        
        # Video file
        for ext in ["mp4", "mkv", "webm", "m4a"]:
            video_path = output_dir / f"video.{ext}"
            if video_path.exists():
                files["video"] = str(video_path)
                break
        
        # Info JSON
        info_path = output_dir / "video.info.json"
        if info_path.exists():
            files["info"] = str(info_path)
        
        # Thumbnail - prefer png > jpg > webp
        for ext in ["png", "jpg", "webp"]:
            thumb_path = output_dir / f"video.{ext}"
            if thumb_path.exists():
                files["thumbnail"] = str(thumb_path)
                break
        
        return files



# ============================================================================
# Metadata Extractor
# ============================================================================

class MetadataExtractor:
    """Extracts metadata from video info JSON."""
    
    @staticmethod
    def extract(info_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from info.json file.
        
        Args:
            info_path: Path to info.json
            
        Returns:
            Extracted metadata dict
        """
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)
        
        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration"),
            "channel_name": info.get("uploader") or info.get("channel"),
            "channel_id": info.get("uploader_id") or info.get("channel_id"),
            "description": info.get("description"),
            "thumbnail_url": info.get("thumbnail"),
            "upload_date": info.get("upload_date"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "extra": {
                "webpage_url": info.get("webpage_url"),
                "extractor": info.get("extractor"),
                "format": info.get("format"),
                "resolution": info.get("resolution"),
                "fps": info.get("fps"),
            }
        }


# ============================================================================
# Download Service
# ============================================================================

class DownloadService(BaseService):
    """
    Video download service.
    
    Implements BaseService interface for worker integration.
    """
    
    def __init__(self, config: Optional[DownloadConfig] = None, download_dir: str = "data/downloads"):
        """
        Initialize download service.
        
        Args:
            config: Download configuration
            download_dir: Directory for downloaded files
        """
        self._config = config or DownloadConfig()
        self._download_dir = download_dir
        self._logger = get_logger("download")
        self._dir_manager = DirectoryManager(self._download_dir)
        
        # Create YtDlpDownloaderConfig with all necessary fields
        yt_dlp_config = YtDlpDownloaderConfig(
            preferred_quality=self._config.preferred_quality,
            download_subtitles=self._config.download_subtitles,
            download_thumbnail=True,
            proxy_url=None,  # Will be set from global config
            cookies_browser=self._config.cookies_browser.value if self._config.cookies_browser else None,
            nodejs_path=self._config.nodejs_path,
            download_dir=download_dir,
        )
        self._yt_dlp = YtDlpDownloader(yt_dlp_config)
        self._current_task_id: Optional[str] = None
    
    async def execute(
        self,
        task: Task,
        progress_callback: ProgressCallback,
        payload_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute download task.
        
        Flow:
        1. Parse URL and validate channel
        2. Fetch metadata first (title, thumbnail) - quick operation
        3. Update task payload with metadata via callback
        4. Execute actual download
        
        Args:
            task: Download task
            progress_callback: Progress callback
            payload_callback: Optional callback to update task payload
            
        Returns:
            Download result
        """
        self._current_task_id = task.id
        payload = task.payload or {}
        
        url = payload.get("url")
        if not url:
            raise DownloadError("URL is required")
        
        channel = DownloadChannel(payload.get("channel", DownloadChannel.YT_DLP.value))
        quality = VideoQuality(payload.get("quality", VideoQuality.BEST.value))
        force_download = payload.get("force_download", False)
        force_h264 = payload.get("force_h264", True)  # Default to H264 for browser compatibility
        
        try:
            # Parse URL
            platform, external_id = URLParser.parse(url)
            self._logger.info(f"Parsed URL: platform={platform.value}, id={external_id}")
            
            # Validate channel
            if not URLParser.validate_channel(channel, platform):
                raise ChannelIncompatibleError(
                    f"Channel {channel.value} does not support {platform.value}"
                )
            
            # Step 1: Fetch metadata first (quick operation, ~5-10 seconds)
            # This allows UI to show video title and thumbnail while downloading
            self._logger.info("Fetching video metadata...")
            metadata = {}
            if channel == DownloadChannel.YT_DLP:
                metadata = await self._yt_dlp.fetch_metadata(url)
                if metadata:
                    self._logger.info(f"Metadata fetched: title={metadata.get('title')}")
                    # Update task payload with metadata
                    if payload_callback:
                        payload_callback({
                            "title": metadata.get("title"),
                            "thumbnail_url": metadata.get("thumbnail_url"),
                            "duration": metadata.get("duration"),
                            "channel_name": metadata.get("channel_name"),
                        })
                else:
                    self._logger.warning("Failed to fetch metadata, continuing with download")
            
            # Generate video ID and create directory
            video_id = str(uuid.uuid4())
            
            # Use fetched title or temp title for directory
            dir_title = metadata.get("title") or f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            output_dir = self._dir_manager.create_video_directory(video_id, dir_title)
            
            self._logger.info(f"Downloading to: {output_dir}")
            
            # Step 2: Execute actual download
            if channel == DownloadChannel.YT_DLP:
                files = await self._yt_dlp.download(
                    url, output_dir, quality, progress_callback, force_h264
                )
            else:
                # BiliDown not implemented yet
                raise DownloadError(f"Channel {channel.value} not implemented")
            
            # Extract full metadata from downloaded info.json
            if "info" in files:
                full_metadata = MetadataExtractor.extract(Path(files["info"]))
                # Merge with pre-fetched metadata
                metadata.update(full_metadata)
            
            # Rename directory with actual title if different
            if metadata.get("title") and metadata["title"] != dir_title:
                new_dir = self._dir_manager.create_video_directory(
                    video_id, metadata["title"]
                )
                if new_dir != output_dir:
                    # Move files to new directory
                    for file_path in output_dir.iterdir():
                        file_path.rename(new_dir / file_path.name)
                    output_dir.rmdir()
                    output_dir = new_dir
                    # Update file paths
                    files = {k: str(output_dir / Path(v).name) for k, v in files.items()}
            
            progress_callback(100)
            
            return {
                "video_id": video_id,
                "directory_path": str(output_dir),
                "files": files,
                "metadata": metadata,
                "platform": platform.value,
                "external_id": external_id,
            }
            
        finally:
            self._current_task_id = None
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel download task."""
        if self._current_task_id == task_id:
            return await self._yt_dlp.cancel()
        return False
    
    def can_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        error_str = str(error).lower()
        
        # Non-retryable errors
        non_retryable = [
            "unsupported url",
            "video unavailable",
            "private video",
            "video has been removed",
            "channel incompatible",
        ]
        if any(msg in error_str for msg in non_retryable):
            return False
        
        # Retryable errors
        retryable = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "http error 5",
            "http error 429",
        ]
        return any(msg in error_str for msg in retryable)
    
    def parse_url(self, url: str) -> Tuple[VideoSource, str]:
        """Parse URL to get platform and video ID."""
        return URLParser.parse(url)
    
    def validate_channel(self, channel: DownloadChannel, platform: VideoSource) -> bool:
        """Validate channel compatibility."""
        return URLParser.validate_channel(channel, platform)
