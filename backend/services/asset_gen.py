"""
Asset Generation Service Module.

Provides asset generation functionality including title generation,
summary generation, and thumbnail generation using LLM APIs and FFmpeg.
"""
import asyncio
import json
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

class LLMProvider(str, Enum):
    """LLM provider types."""
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    OPENAI = "openai"


class ThumbnailMode(str, Enum):
    """Thumbnail generation modes."""
    FRAME = "frame"
    AI = "ai"


class SummaryStyle(str, Enum):
    """Summary output styles."""
    PLAIN = "plain"
    STRUCTURED = "structured"


class TargetPlatform(str, Enum):
    """Target platform for title generation."""
    GENERAL = "general"
    YOUTUBE = "youtube"
    BILIBILI = "bilibili"
    TIKTOK = "tiktok"


# ============================================================================
# Exceptions
# ============================================================================

class AssetGenError(Exception):
    """Base asset generation error."""
    pass


class SubtitleNotFoundError(AssetGenError):
    """Subtitle file not found."""
    pass


class LLMError(AssetGenError):
    """LLM API error."""
    pass


class AllInstancesFailedError(AssetGenError):
    """All LLM instances failed."""
    pass


class ThumbnailError(AssetGenError):
    """Thumbnail generation error."""
    pass


class FFmpegError(AssetGenError):
    """FFmpeg execution error."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class LLMInstance:
    """LLM instance configuration for asset generation."""
    name: str
    provider: LLMProvider
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.8  # Higher for creative tasks
    enabled: bool = True
    priority: int = 100


@dataclass
class ImageGenInstance:
    """Image generation service configuration."""
    name: str
    provider: str  # dall-e, midjourney, stable-diffusion
    api_key: str
    base_url: str
    model: str
    enabled: bool = True


@dataclass
class TitleConfig:
    """Title generation configuration."""
    candidate_count: int = 5
    target_platform: TargetPlatform = TargetPlatform.GENERAL
    include_emoji: bool = False
    max_length: int = 80


@dataclass
class SummaryConfig:
    """Summary generation configuration."""
    style: SummaryStyle = SummaryStyle.PLAIN
    max_length: int = 500
    include_timestamps: bool = False


@dataclass
class ThumbnailConfig:
    """Thumbnail generation configuration."""
    mode: ThumbnailMode = ThumbnailMode.FRAME
    frame_time: str = "auto"  # "auto" or specific time like "00:01:30"
    frame_count: int = 1
    output_width: int = 1920
    output_height: int = 1080
    image_quality: int = 90
    ai_provider: str = "dall-e"
    ai_style: str = "realistic"


@dataclass
class AssetGenConfig:
    """Asset generation service configuration."""
    generate_title: bool = True
    generate_summary: bool = True
    generate_thumbnail: bool = True
    use_translated_subtitle: bool = True
    summary_head_seconds: int = 30
    summary_tail_seconds: int = 30
    temperature_title: float = 0.85
    temperature_summary: float = 0.65
    temperature_thumbnail: float = 0.7
    llm_instances: List[LLMInstance] = field(default_factory=list)
    thumbnail_llm_instance: Optional[LLMInstance] = None  # Separate LLM for thumbnail prompt generation
    image_gen_instance: Optional[ImageGenInstance] = None
    title_config: TitleConfig = field(default_factory=TitleConfig)
    summary_config: SummaryConfig = field(default_factory=SummaryConfig)
    thumbnail_config: ThumbnailConfig = field(default_factory=ThumbnailConfig)
    ffmpeg_path: str = "ffmpeg"


# ============================================================================
# SRT Parser (for subtitle extraction)
# ============================================================================

class SubtitleExtractor:
    """Extracts and processes subtitle content for asset generation."""
    
    # Pattern for SRT timestamp line
    TIMESTAMP_PATTERN = re.compile(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    )
    
    def __init__(self):
        self._logger = get_logger("asset_gen.subtitle")
    
    def parse_srt(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Parse SRT file into entries with timestamps.
        
        Returns:
            List of dicts with keys: index, start_seconds, end_seconds, text
        """
        if not file_path.exists():
            raise SubtitleNotFoundError(f"Subtitle file not found: {file_path}")
        
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
                timestamp_match = self.TIMESTAMP_PATTERN.match(lines[1].strip())
                if not timestamp_match:
                    continue
                
                # Parse start time to seconds
                sh, sm, ss, sms = map(int, timestamp_match.groups()[:4])
                start_seconds = sh * 3600 + sm * 60 + ss + sms / 1000
                
                # Parse end time to seconds
                eh, em, es, ems = map(int, timestamp_match.groups()[4:])
                end_seconds = eh * 3600 + em * 60 + es + ems / 1000
                
                text = '\n'.join(lines[2:]).strip()
                
                if text:
                    entries.append({
                        "index": index,
                        "start_seconds": start_seconds,
                        "end_seconds": end_seconds,
                        "text": text,
                    })
            except (ValueError, IndexError):
                continue
        
        self._logger.info(f"Parsed {len(entries)} subtitle entries")
        return entries

    
    def extract_head_tail(
        self,
        entries: List[Dict[str, Any]],
        head_seconds: int = 30,
        tail_seconds: int = 30,
    ) -> Tuple[str, str]:
        """
        Extract head and tail portions of subtitle for summary generation.
        
        Args:
            entries: Parsed subtitle entries
            head_seconds: Seconds from start to include
            tail_seconds: Seconds from end to include
            
        Returns:
            Tuple of (head_text, tail_text)
        """
        if not entries:
            return "", ""
        
        # Get total duration
        total_duration = entries[-1]["end_seconds"]
        
        # If video is short, return all text
        if total_duration < head_seconds + tail_seconds + 30:
            all_text = " ".join(e["text"] for e in entries)
            return all_text, ""
        
        # Extract head portion
        head_entries = [
            e for e in entries
            if e["start_seconds"] < head_seconds
        ]
        head_text = " ".join(e["text"] for e in head_entries)
        
        # Extract tail portion
        tail_start = total_duration - tail_seconds
        tail_entries = [
            e for e in entries
            if e["start_seconds"] >= tail_start
        ]
        tail_text = " ".join(e["text"] for e in tail_entries)
        
        self._logger.info(
            f"Extracted head ({len(head_entries)} entries) and "
            f"tail ({len(tail_entries)} entries) from {len(entries)} total"
        )
        
        return head_text, tail_text
    
    def get_full_text(self, entries: List[Dict[str, Any]]) -> str:
        """Get full subtitle text."""
        return " ".join(e["text"] for e in entries)


# ============================================================================
# LLM Providers
# ============================================================================

class BaseLLMProvider:
    """Base class for LLM providers."""
    
    def __init__(self, instance: LLMInstance):
        self._instance = instance
        self._logger = get_logger(f"asset_gen.{instance.provider.value}")
    
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using LLM."""
        raise NotImplementedError


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API provider."""
    
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
    ) -> str:
        """Generate using DeepSeek API."""
        try:
            import httpx
        except ImportError:
            raise LLMError("httpx is required for DeepSeek API")
        
        temp = temperature if temperature is not None else self._instance.temperature
        
        headers = {
            "Authorization": f"Bearer {self._instance.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._instance.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
            "max_tokens": max_tokens,
        }
        
        url = f"{self._instance.base_url.rstrip('/')}/chat/completions"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise LLMError(f"DeepSeek API error: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""
    
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
    ) -> str:
        """Generate using OpenAI API."""
        try:
            import httpx
        except ImportError:
            raise LLMError("httpx is required for OpenAI API")
        
        temp = temperature if temperature is not None else self._instance.temperature
        
        headers = {
            "Authorization": f"Bearer {self._instance.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._instance.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
            "max_tokens": max_tokens,
        }
        
        url = f"{self._instance.base_url.rstrip('/')}/chat/completions"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise LLMError(f"OpenAI API error: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider."""
    
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
    ) -> str:
        """Generate using Gemini API."""
        try:
            import httpx
        except ImportError:
            raise LLMError("httpx is required for Gemini API")
        
        temp = temperature if temperature is not None else self._instance.temperature
        
        url = f"{self._instance.base_url.rstrip('/')}/models/{self._instance.model}:generateContent"
        url = f"{url}?key={self._instance.api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temp,
                "maxOutputTokens": max_tokens,
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
        
        if response.status_code != 200:
            raise LLMError(f"Gemini API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Failed to parse Gemini response: {e}")


def create_llm_provider(instance: LLMInstance) -> BaseLLMProvider:
    """Factory function to create LLM provider."""
    providers = {
        LLMProvider.DEEPSEEK: DeepSeekProvider,
        LLMProvider.OPENAI: OpenAIProvider,
        LLMProvider.GEMINI: GeminiProvider,
    }
    
    provider_class = providers.get(instance.provider)
    if not provider_class:
        raise LLMError(f"Unknown provider: {instance.provider}")
    
    return provider_class(instance)


# ============================================================================
# LLM Instance Manager
# ============================================================================

class LLMInstanceManager:
    """Manages LLM instances with priority-based failover."""
    
    def __init__(self, instances: List[LLMInstance]):
        # Sort by priority (lower number = higher priority)
        self._instances = sorted(
            [i for i in instances if i.enabled],
            key=lambda x: x.priority
        )
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._logger = get_logger("asset_gen.manager")
        
        # Create providers
        for instance in self._instances:
            self._providers[instance.name] = create_llm_provider(instance)
        
        self._logger.info(f"Loaded {len(self._instances)} LLM instances")
    
    async def generate_with_failover(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> Tuple[str, str]:
        """
        Generate text with failover across instances.
        
        Returns:
            Tuple of (generated_text, provider_name_used)
        """
        if not self._instances:
            raise AllInstancesFailedError("No LLM instances configured")
        
        errors = []
        
        for instance in self._instances:
            provider = self._providers[instance.name]
            
            for attempt in range(max_retries + 1):
                try:
                    self._logger.info(f"Trying {instance.name} (attempt {attempt + 1})")
                    result = await provider.generate(prompt, temperature, max_tokens)
                    return result, instance.name
                    
                except LLMError as e:
                    self._logger.warning(f"{instance.name} error: {e}")
                    errors.append(f"{instance.name}: {e}")
                    
                    if attempt < max_retries:
                        delay = retry_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    
                except Exception as e:
                    self._logger.error(f"{instance.name} unexpected error: {e}")
                    errors.append(f"{instance.name}: {e}")
                    break
        
        raise AllInstancesFailedError(f"All instances failed: {'; '.join(errors)}")
    
    def has_providers(self) -> bool:
        """Check if any providers are available."""
        return len(self._instances) > 0


# ============================================================================
# Title Generator
# ============================================================================

class TitleGenerator:
    """Generates title candidates using LLM."""
    
    PLATFORM_HINTS = {
        TargetPlatform.GENERAL: "general audience",
        TargetPlatform.YOUTUBE: "YouTube (engaging, clickable, SEO-friendly)",
        TargetPlatform.BILIBILI: "Bilibili (Chinese platform, trendy, youth-oriented)",
        TargetPlatform.TIKTOK: "TikTok (short, catchy, viral potential)",
    }
    
    def __init__(self, manager: LLMInstanceManager, config: TitleConfig):
        self._manager = manager
        self._config = config
        self._logger = get_logger("asset_gen.title")
    
    def _build_prompt(
        self,
        original_title: str,
        content_summary: str,
        channel_name: Optional[str] = None,
    ) -> str:
        """Build title generation prompt."""
        platform_hint = self.PLATFORM_HINTS.get(
            self._config.target_platform, "general audience"
        )
        
        emoji_instruction = (
            "Include relevant emojis to make titles more engaging."
            if self._config.include_emoji
            else "Do NOT include emojis in the titles."
        )
        
        prompt = f"""You are a professional video title creator. Generate {self._config.candidate_count} compelling title candidates for a video.

Original Title: {original_title}
Target Platform: {platform_hint}
Maximum Length: {self._config.max_length} characters

Video Content Summary:
{content_summary[:1000]}

Requirements:
- Create {self._config.candidate_count} unique title candidates
- Each title should be attention-grabbing and relevant
- Keep titles under {self._config.max_length} characters
- {emoji_instruction}
- Optimize for the target platform's style
- Output ONLY the titles, one per line, numbered (e.g., "1. Title here")
"""
        
        if channel_name:
            prompt += f"\nChannel: {channel_name}\n"
        
        return prompt
    
    async def generate(
        self,
        original_title: str,
        content_summary: str,
        channel_name: Optional[str] = None,
        temperature: float = 0.85,
    ) -> List[str]:
        """
        Generate title candidates.
        
        Returns:
            List of title candidates
        """
        prompt = self._build_prompt(original_title, content_summary, channel_name)
        
        response, provider = await self._manager.generate_with_failover(
            prompt, temperature=temperature, max_tokens=1024
        )
        
        self._logger.info(f"Generated titles via {provider}")
        
        # Parse response
        titles = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Remove number prefix
            cleaned = re.sub(r'^\d+[\.\:\)\-]\s*', '', line)
            if cleaned and len(cleaned) <= self._config.max_length:
                titles.append(cleaned)
        
        return titles[:self._config.candidate_count]


# ============================================================================
# Summary Generator
# ============================================================================

class SummaryGenerator:
    """Generates video summary using LLM."""
    
    def __init__(self, manager: LLMInstanceManager, config: SummaryConfig):
        self._manager = manager
        self._config = config
        self._logger = get_logger("asset_gen.summary")
    
    def _build_prompt(
        self,
        video_title: str,
        head_text: str,
        tail_text: str,
    ) -> str:
        """Build summary generation prompt."""
        style_instruction = (
            "Output a single continuous paragraph."
            if self._config.style == SummaryStyle.PLAIN
            else "Output with section headers and bullet points for key topics."
        )
        
        timestamp_instruction = (
            "Include approximate timestamps for key points."
            if self._config.include_timestamps
            else ""
        )
        
        prompt = f"""You are a professional content summarizer. Generate a concise summary for a video based on its subtitle content.

Video Title: {video_title}

Note: The following are excerpts from the video's beginning and ending portions.

Opening Content (first ~30 seconds):
{head_text[:2000] if head_text else "(Not available)"}

Closing Content (last ~30 seconds):
{tail_text[:2000] if tail_text else "(Not available)"}

Requirements:
- Create a summary of approximately {self._config.max_length} characters
- Capture the main topic and key points
- {style_instruction}
- {timestamp_instruction}
- Be accurate and informative
- Write in the same language as the subtitle content
"""
        
        return prompt
    
    async def generate(
        self,
        video_title: str,
        head_text: str,
        tail_text: str,
        temperature: float = 0.65,
    ) -> str:
        """
        Generate video summary.
        
        Returns:
            Summary text
        """
        prompt = self._build_prompt(video_title, head_text, tail_text)
        
        response, provider = await self._manager.generate_with_failover(
            prompt, temperature=temperature, max_tokens=1024
        )
        
        self._logger.info(f"Generated summary via {provider}")
        
        # Clean up response
        summary = response.strip()
        
        # Truncate if too long
        if len(summary) > self._config.max_length * 1.5:
            summary = summary[:self._config.max_length] + "..."
        
        return summary


# ============================================================================
# Thumbnail Generator
# ============================================================================

class ThumbnailGenerator:
    """Generates thumbnails via video frame extraction or AI generation."""
    
    def __init__(
        self,
        config: ThumbnailConfig,
        ffmpeg_path: str = "ffmpeg",
        image_gen_instance: Optional[ImageGenInstance] = None,
        llm_manager: Optional[LLMInstanceManager] = None,
        thumbnail_llm_instance: Optional[LLMInstance] = None,
    ):
        self._config = config
        self._ffmpeg_path = ffmpeg_path
        self._image_gen = image_gen_instance
        self._llm_manager = llm_manager
        self._thumbnail_llm_instance = thumbnail_llm_instance  # Dedicated LLM for thumbnail prompts
        self._thumbnail_llm_provider: Optional[BaseLLMProvider] = None
        self._logger = get_logger("asset_gen.thumbnail")
        
        # Initialize dedicated thumbnail LLM provider if configured
        if self._thumbnail_llm_instance:
            self._thumbnail_llm_provider = create_llm_provider(self._thumbnail_llm_instance)
    
    async def generate(
        self,
        video_path: Path,
        output_path: Path,
        video_title: Optional[str] = None,
        content_summary: Optional[str] = None,
    ) -> Path:
        """
        Generate thumbnail.
        
        Args:
            video_path: Path to video file
            output_path: Output thumbnail path
            video_title: Video title (for AI generation)
            content_summary: Content summary (for AI generation)
            
        Returns:
            Path to generated thumbnail
        """
        # Check if AI mode is enabled and properly configured
        has_llm = self._thumbnail_llm_provider or self._llm_manager
        if self._config.mode == ThumbnailMode.AI and self._image_gen and has_llm:
            try:
                return await self._generate_ai_thumbnail(
                    output_path, video_title, content_summary
                )
            except Exception as e:
                self._logger.warning(f"AI thumbnail failed, falling back to frame: {e}")
        
        # Default to frame extraction
        return await self._extract_frame(video_path, output_path)
    
    async def _extract_frame(self, video_path: Path, output_path: Path) -> Path:
        """Extract frame from video using FFmpeg."""
        # Get video duration first
        duration = await self._get_video_duration(video_path)
        
        # Determine frame time
        if self._config.frame_time == "auto":
            # Use 10% into the video as default
            frame_time = duration * 0.1
            frame_time = max(1.0, min(frame_time, duration - 1))
        else:
            # Parse time string (HH:MM:SS or seconds)
            frame_time = self._parse_time(self._config.frame_time)
        
        # Build FFmpeg command
        cmd = [
            self._ffmpeg_path,
            "-ss", str(frame_time),
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", f"scale={self._config.output_width}:{self._config.output_height}:force_original_aspect_ratio=decrease,pad={self._config.output_width}:{self._config.output_height}:(ow-iw)/2:(oh-ih)/2",
            "-q:v", str(max(1, min(31, 31 - int(self._config.image_quality * 0.3)))),
            "-y",
            str(output_path),
        ]
        
        self._logger.info(f"Extracting frame at {frame_time}s from {video_path}")
        
        # Run FFmpeg in thread pool (Windows compatible)
        import subprocess
        
        def _run_ffmpeg():
            return subprocess.run(
                cmd,
                capture_output=True,
            )
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_ffmpeg)
        
        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="replace")
            raise FFmpegError(f"Frame extraction failed: {error_msg}")
        
        if not output_path.exists():
            raise ThumbnailError("Thumbnail file not created")
        
        self._logger.info(f"Extracted thumbnail: {output_path}")
        return output_path

    
    async def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration using FFmpeg."""
        import subprocess
        
        cmd = [
            self._ffmpeg_path,
            "-i", str(video_path),
            "-f", "null", "-"
        ]
        
        # Run FFmpeg in thread pool (Windows compatible)
        def _run_ffmpeg():
            return subprocess.run(
                cmd,
                capture_output=True,
            )
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_ffmpeg)
        output = result.stderr.decode("utf-8", errors="replace")
        
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
        if match:
            h, m, s, cs = map(int, match.groups())
            return h * 3600 + m * 60 + s + cs / 100
        
        return 60.0  # Default fallback
    
    def _parse_time(self, time_str: str) -> float:
        """Parse time string to seconds."""
        # Try HH:MM:SS format
        match = re.match(r'(\d+):(\d+):(\d+)', time_str)
        if match:
            h, m, s = map(int, match.groups())
            return h * 3600 + m * 60 + s
        
        # Try MM:SS format
        match = re.match(r'(\d+):(\d+)', time_str)
        if match:
            m, s = map(int, match.groups())
            return m * 60 + s
        
        # Try seconds
        try:
            return float(time_str)
        except ValueError:
            return 10.0  # Default
    
    async def _generate_ai_thumbnail(
        self,
        output_path: Path,
        video_title: Optional[str],
        content_summary: Optional[str],
    ) -> Path:
        """Generate thumbnail using AI image generation."""
        # Check if we have LLM for prompt generation (either dedicated or shared)
        has_llm = self._thumbnail_llm_provider or self._llm_manager
        if not self._image_gen or not has_llm:
            raise ThumbnailError("AI thumbnail generation not configured (need both LLM and image API)")
        
        # Generate image prompt using LLM
        prompt = await self._generate_image_prompt(video_title, content_summary)
        
        # Call image generation API
        image_data = await self._call_image_api(prompt)
        
        # Save image
        output_path.write_bytes(image_data)
        
        self._logger.info(f"Generated AI thumbnail: {output_path}")
        return output_path
    
    async def _generate_image_prompt(
        self,
        video_title: Optional[str],
        content_summary: Optional[str],
    ) -> str:
        """Generate image prompt using LLM."""
        llm_prompt = f"""Generate a detailed image generation prompt for a video thumbnail.

Video Title: {video_title or "Unknown"}
Content Summary: {content_summary[:500] if content_summary else "Not available"}

Requirements:
- Create a descriptive English prompt for image generation
- Include style, composition, colors, and mood
- Style: {self._config.ai_style}
- Make it visually appealing for a video thumbnail
- Output ONLY the image prompt, nothing else
"""
        
        # Use dedicated thumbnail LLM if available, otherwise fall back to shared manager
        if self._thumbnail_llm_provider:
            temperature = self._thumbnail_llm_instance.temperature if self._thumbnail_llm_instance else 0.7
            response = await self._thumbnail_llm_provider.generate(
                llm_prompt, temperature=temperature, max_tokens=256
            )
            self._logger.info(f"Generated image prompt using dedicated thumbnail LLM")
        elif self._llm_manager:
            response, provider_name = await self._llm_manager.generate_with_failover(
                llm_prompt, temperature=0.7, max_tokens=256
            )
            self._logger.info(f"Generated image prompt using shared LLM: {provider_name}")
        else:
            raise ThumbnailError("No LLM configured for image prompt generation")
        
        return response.strip()
    
    async def _call_image_api(self, prompt: str) -> bytes:
        """Call image generation API."""
        try:
            import httpx
        except ImportError:
            raise ThumbnailError("httpx is required for AI image generation")
        
        if self._image_gen.provider == "dall-e":
            return await self._call_dalle(prompt)
        else:
            raise ThumbnailError(f"Unsupported image provider: {self._image_gen.provider}")

    
    async def _call_dalle(self, prompt: str) -> bytes:
        """Call DALL-E API for image generation."""
        import httpx
        
        headers = {
            "Authorization": f"Bearer {self._image_gen.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._image_gen.model or "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": f"{self._config.output_width}x{self._config.output_height}",
            "response_format": "b64_json",
        }
        
        url = f"{self._image_gen.base_url.rstrip('/')}/images/generations"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise ThumbnailError(f"DALL-E API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        import base64
        image_b64 = result["data"][0]["b64_json"]
        return base64.b64decode(image_b64)


# ============================================================================
# Asset Generation Service
# ============================================================================

class AssetGenService(BaseService):
    """
    Asset generation service.
    
    Implements BaseService interface for worker integration.
    Generates titles, summaries, and thumbnails for videos.
    """
    
    # Progress allocation for full generation
    PROGRESS_PREPARE = 5
    PROGRESS_TITLE = 30
    PROGRESS_SUMMARY = 40
    PROGRESS_THUMBNAIL = 25
    
    def __init__(self, config: Optional[AssetGenConfig] = None):
        """
        Initialize asset generation service.
        
        Args:
            config: Asset generation configuration
        """
        self._config = config or AssetGenConfig()
        self._logger = get_logger("asset_gen")
        self._subtitle_extractor = SubtitleExtractor()
        self._llm_manager: Optional[LLMInstanceManager] = None
        self._title_generator: Optional[TitleGenerator] = None
        self._summary_generator: Optional[SummaryGenerator] = None
        self._thumbnail_generator: Optional[ThumbnailGenerator] = None
        self._current_task_id: Optional[str] = None
        self._cancelled = False
    
    def _init_components(self) -> None:
        """Initialize service components."""
        if self._llm_manager is None and self._config.llm_instances:
            self._llm_manager = LLMInstanceManager(self._config.llm_instances)
            self._title_generator = TitleGenerator(
                self._llm_manager, self._config.title_config
            )
            self._summary_generator = SummaryGenerator(
                self._llm_manager, self._config.summary_config
            )
        
        if self._thumbnail_generator is None:
            self._thumbnail_generator = ThumbnailGenerator(
                self._config.thumbnail_config,
                self._config.ffmpeg_path,
                self._config.image_gen_instance,
                self._llm_manager,
                self._config.thumbnail_llm_instance,  # Pass dedicated thumbnail LLM
            )
    
    async def execute(
        self,
        task: Task,
        progress_callback: ProgressCallback,
        payload_callback=None,
    ) -> Dict[str, Any]:
        """
        Execute asset generation task.
        
        Args:
            task: Asset generation task
            progress_callback: Progress callback
            payload_callback: Optional callback to update task payload (unused)
            
        Returns:
            Generation result
        """
        self._current_task_id = task.id
        self._cancelled = False
        payload = task.payload or {}
        
        video_id = payload.get("video_id")
        video_path = payload.get("video_path")
        subtitle_path = payload.get("subtitle_path")
        
        if not video_path:
            raise AssetGenError("video_path is required")
        
        video_path = Path(video_path)
        if not video_path.exists():
            raise AssetGenError(f"Video file not found: {video_path}")
        
        # Determine which assets to generate
        gen_title = payload.get("generate_title", self._config.generate_title)
        gen_summary = payload.get("generate_summary", self._config.generate_summary)
        gen_thumbnail = payload.get("generate_thumbnail", self._config.generate_thumbnail)
        
        # Calculate progress weights based on enabled features
        progress_weights = self._calculate_progress_weights(
            gen_title, gen_summary, gen_thumbnail
        )

        
        # Create assets directory
        assets_dir = video_path.parent / "assets"
        assets_dir.mkdir(exist_ok=True)
        
        # Get video metadata
        video_title = payload.get("video_title", video_path.stem)
        channel_name = payload.get("channel_name")
        
        result = {
            "video_id": video_id,
            "generated_items": [],
            "title_candidates_path": None,
            "summary_path": None,
            "thumbnail_path": None,
        }
        
        try:
            self._init_components()
            
            progress_callback(0)
            current_progress = 0
            
            # Parse subtitle if needed for title/summary
            subtitle_entries = []
            head_text = ""
            tail_text = ""
            full_text = ""
            
            if (gen_title or gen_summary) and subtitle_path:
                subtitle_path = Path(subtitle_path)
                if subtitle_path.exists():
                    self._logger.info(f"Parsing subtitle: {subtitle_path}")
                    subtitle_entries = self._subtitle_extractor.parse_srt(subtitle_path)
                    
                    head_text, tail_text = self._subtitle_extractor.extract_head_tail(
                        subtitle_entries,
                        self._config.summary_head_seconds,
                        self._config.summary_tail_seconds,
                    )
                    full_text = self._subtitle_extractor.get_full_text(subtitle_entries)
            
            current_progress = progress_weights["prepare"]
            progress_callback(current_progress)
            
            # Generate title candidates
            if gen_title and self._title_generator:
                if self._cancelled:
                    raise AssetGenError("Generation cancelled")
                
                self._logger.info("Generating title candidates...")
                content_for_title = head_text or full_text[:2000]
                
                titles = await self._title_generator.generate(
                    video_title,
                    content_for_title,
                    channel_name,
                    self._config.temperature_title,
                )
                
                # Save titles
                title_path = assets_dir / "title_candidates.txt"
                title_path.write_text("\n".join(titles), encoding="utf-8")
                
                result["title_candidates_path"] = str(title_path)
                result["generated_items"].append("title")
                
                self._logger.info(f"Generated {len(titles)} title candidates")
                
                current_progress += progress_weights["title"]
                progress_callback(current_progress)

            
            # Generate summary
            if gen_summary and self._summary_generator:
                if self._cancelled:
                    raise AssetGenError("Generation cancelled")
                
                self._logger.info("Generating summary...")
                
                summary = await self._summary_generator.generate(
                    video_title,
                    head_text,
                    tail_text,
                    self._config.temperature_summary,
                )
                
                # Save summary
                summary_path = assets_dir / "summary.txt"
                summary_path.write_text(summary, encoding="utf-8")
                
                result["summary_path"] = str(summary_path)
                result["generated_items"].append("summary")
                
                self._logger.info(f"Generated summary ({len(summary)} chars)")
                
                current_progress += progress_weights["summary"]
                progress_callback(current_progress)
            
            # Generate thumbnail
            if gen_thumbnail and self._thumbnail_generator:
                if self._cancelled:
                    raise AssetGenError("Generation cancelled")
                
                self._logger.info("Generating thumbnail...")
                
                thumbnail_path = assets_dir / "thumbnail.jpg"
                
                await self._thumbnail_generator.generate(
                    video_path,
                    thumbnail_path,
                    video_title,
                    head_text or full_text[:500],
                )
                
                result["thumbnail_path"] = str(thumbnail_path)
                result["generated_items"].append("thumbnail")
                
                self._logger.info(f"Generated thumbnail: {thumbnail_path}")
            
            progress_callback(100)
            
            return result
            
        finally:
            self._current_task_id = None
    
    def _calculate_progress_weights(
        self,
        gen_title: bool,
        gen_summary: bool,
        gen_thumbnail: bool,
    ) -> Dict[str, int]:
        """Calculate progress weights based on enabled features."""
        weights = {"prepare": self.PROGRESS_PREPARE}
        
        enabled_count = sum([gen_title, gen_summary, gen_thumbnail])
        if enabled_count == 0:
            return {"prepare": 100, "title": 0, "summary": 0, "thumbnail": 0}
        
        remaining = 100 - self.PROGRESS_PREPARE
        
        if enabled_count == 3:
            # Full generation
            weights["title"] = self.PROGRESS_TITLE
            weights["summary"] = self.PROGRESS_SUMMARY
            weights["thumbnail"] = self.PROGRESS_THUMBNAIL
        else:
            # Distribute remaining progress among enabled features
            per_feature = remaining // enabled_count
            weights["title"] = per_feature if gen_title else 0
            weights["summary"] = per_feature if gen_summary else 0
            weights["thumbnail"] = per_feature if gen_thumbnail else 0
        
        return weights

    
    async def cancel(self, task_id: str) -> bool:
        """Cancel asset generation task."""
        if self._current_task_id != task_id:
            return False
        
        self._cancelled = True
        return True
    
    def can_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        error_str = str(error).lower()
        
        # Non-retryable errors
        non_retryable = [
            "file not found",
            "video file not found",
            "subtitle file not found",
            "no llm instances configured",
            "all instances failed",
            "cancelled",
        ]
        if any(msg in error_str for msg in non_retryable):
            return False
        
        # Retryable errors
        retryable = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "temporary",
        ]
        return any(msg in error_str for msg in retryable)
    
    # Utility methods for external use
    async def generate_titles(
        self,
        original_title: str,
        content: str,
        channel_name: Optional[str] = None,
        config: Optional[TitleConfig] = None,
    ) -> List[str]:
        """Generate title candidates (standalone method)."""
        self._init_components()
        
        if not self._title_generator:
            raise AssetGenError("LLM instances not configured")
        
        if config:
            self._title_generator._config = config
        
        return await self._title_generator.generate(
            original_title, content, channel_name, self._config.temperature_title
        )
    
    async def generate_summary(
        self,
        video_title: str,
        subtitle_path: Path,
        config: Optional[SummaryConfig] = None,
    ) -> str:
        """Generate summary (standalone method)."""
        self._init_components()
        
        if not self._summary_generator:
            raise AssetGenError("LLM instances not configured")
        
        if config:
            self._summary_generator._config = config
        
        entries = self._subtitle_extractor.parse_srt(subtitle_path)
        head_text, tail_text = self._subtitle_extractor.extract_head_tail(
            entries,
            self._config.summary_head_seconds,
            self._config.summary_tail_seconds,
        )
        
        return await self._summary_generator.generate(
            video_title, head_text, tail_text, self._config.temperature_summary
        )
    
    async def generate_thumbnail(
        self,
        video_path: Path,
        output_path: Path,
        config: Optional[ThumbnailConfig] = None,
    ) -> Path:
        """Generate thumbnail (standalone method)."""
        self._init_components()
        
        if not self._thumbnail_generator:
            self._thumbnail_generator = ThumbnailGenerator(
                config or self._config.thumbnail_config,
                self._config.ffmpeg_path,
            )
        elif config:
            self._thumbnail_generator._config = config
        
        return await self._thumbnail_generator.generate(video_path, output_path)
