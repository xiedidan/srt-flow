"""
TTS (Text-to-Speech) Service Module.

Provides speech synthesis functionality using multiple TTS engines
with speed calculation and audio concatenation support.
"""
import asyncio
import io
import re
import struct
import subprocess
import wave
from abc import ABC, abstractmethod
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

class TTSEngine(str, Enum):
    """Supported TTS engines."""
    CHATTTS = "chattts"
    COQUI = "coqui"
    SPARKTTS = "sparktts"
    INDEXTTS = "indextts"
    COZYVOICE = "cozyvoice"
    VITS = "vits"
    # Online TTS services
    AZURE_TTS = "azure_tts"
    EDGE_TTS = "edge_tts"
    VOLC_TTS = "volc_tts"


class OutputFormat(str, Enum):
    """Audio output formats."""
    WAV = "wav"
    M4A = "m4a"
    MP3 = "mp3"


# Split punctuation for long text
SPLIT_PUNCTUATION = "。！？，、；：.!?,;:"


# ============================================================================
# Exceptions
# ============================================================================

class TTSError(Exception):
    """Base TTS error."""
    pass


class EngineLoadError(TTSError):
    """Engine loading failed."""
    pass


class SynthesisError(TTSError):
    """Speech synthesis failed."""
    pass


class AudioProcessError(TTSError):
    """Audio processing failed."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SubtitleEntry:
    """Subtitle entry for TTS."""
    index: int
    start_time: float  # seconds
    end_time: float    # seconds
    text: str
    
    @property
    def duration(self) -> float:
        """Get subtitle duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class AudioSegment:
    """Audio segment data."""
    data: bytes
    sample_rate: int
    channels: int = 1
    sample_width: int = 2  # 16-bit
    
    @property
    def duration(self) -> float:
        """Get audio duration in seconds."""
        return len(self.data) / (self.sample_rate * self.channels * self.sample_width)


@dataclass
class TTSConfig:
    """TTS service configuration."""
    engine: TTSEngine = TTSEngine.CHATTTS
    model_path: Optional[str] = None
    speaker: Optional[str] = None
    output_format: OutputFormat = OutputFormat.M4A
    output_bitrate: str = "128k"
    use_gpu: bool = True
    gpu_device_id: int = 0
    max_chars_per_segment: int = 100
    base_chars_per_second: float = 4.0
    min_speed: float = 0.5
    max_speed: float = 2.0
    enable_time_stretch: bool = True
    ffmpeg_path: str = "ffmpeg"
    
    # Proxy settings for online TTS services
    proxy_url: Optional[str] = None
    
    # Reference audio for voice cloning
    reference_audio: Optional[str] = None
    
    # ChatTTS settings
    chattts_temperature: float = 0.3
    chattts_top_p: float = 0.7
    chattts_top_k: int = 20
    
    # IndexTTS settings
    indextts_mode: str = "local"  # "local" or "api"
    indextts_api_url: Optional[str] = None
    
    # SparkTTS settings
    sparktts_mode: str = "local"
    sparktts_api_url: Optional[str] = None
    
    # CozyVoice settings
    cozyvoice_mode: str = "local"
    cozyvoice_api_url: Optional[str] = None
    cozyvoice_speaker: str = "中文女"
    
    # Coqui TTS settings
    coqui_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    
    # VITS settings
    vits_model_path: Optional[str] = None
    
    # Azure TTS settings (online service)
    azure_tts_voice: str = "zh-CN-XiaoxiaoMultilingualNeural"
    azure_tts_style: str = "general"
    azure_tts_rate: str = "0"  # Percentage, e.g., "0", "+10", "-10"
    azure_tts_pitch: str = "0"  # Percentage
    
    # Edge TTS settings (online service)
    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_tts_rate: str = "+0%"  # e.g., "+0%", "+10%", "-10%"
    edge_tts_pitch: str = "+0Hz"  # e.g., "+0Hz", "+10Hz"
    
    # Volc TTS settings (online service)
    volc_tts_voice: str = "zh_female_qingxin"


# ============================================================================
# SRT Parser (reuse from translator but simplified)
# ============================================================================

class TTSSRTParser:
    """Parses SRT files for TTS processing."""
    
    TIMESTAMP_PATTERN = re.compile(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    )
    
    def parse(self, file_path: Path) -> List[SubtitleEntry]:
        """Parse SRT file into subtitle entries."""
        if not file_path.exists():
            raise TTSError(f"SRT file not found: {file_path}")
        
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
                
                # Parse timestamps to seconds
                start = self._parse_timestamp(match.groups()[:4])
                end = self._parse_timestamp(match.groups()[4:])
                text = '\n'.join(lines[2:]).strip()
                
                if text:
                    entries.append(SubtitleEntry(index, start, end, text))
            except (ValueError, IndexError):
                continue
        
        return entries
    
    def _parse_timestamp(self, parts: Tuple) -> float:
        """Convert timestamp parts to seconds."""
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000


# ============================================================================
# Sentence Merger (AI-powered)
# ============================================================================

@dataclass
class MergedSubtitleEntry:
    """Merged subtitle entry with original indices mapping."""
    merged_text: str
    original_indices: List[int]  # Indices of original entries that were merged
    start_time: float
    end_time: float


class SentenceMergeError(TTSError):
    """Sentence merge failed."""
    pass


class SentenceMerger:
    """
    AI-powered sentence merger for TTS.
    
    Merges fragmented subtitle entries into complete sentences
    for more natural speech synthesis.
    
    Uses a two-stage approach:
    1. AI determines merge groups (returns only indices)
    2. Local processing merges text based on groups
    """
    
    # Batch size threshold for splitting (conservative for 128K context)
    DEFAULT_BATCH_SIZE = 4000
    
    DEFAULT_SYSTEM_PROMPT = """你是一个字幕句子合并助手。你的任务是判断哪些相邻的字幕片段属于同一个完整句子。

规则：
1. 分析输入的字幕列表，识别哪些相邻片段属于同一句子
2. 只输出合并分组，不要输出合并后的文本
3. 输出格式：用竖线分隔不同的组，组内用逗号分隔序号
4. 示例：1,2,3|4,5|6|7,8,9 表示第1-3条合并、第4-5条合并、第6条独立、第7-9条合并
5. 不要添加任何解释，只输出分组结果

示例输入：
1. 今天天气
2. 真的很好
3. 我们去公园吧
4. 好的，
5. 明天见

示例输出：
1,2|3,4|5"""

    DEFAULT_USER_PROMPT = """请判断以下字幕片段的合并关系，只输出序号分组：

{subtitles}"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip('/') if base_url else ""
        self._model = model
        self._temperature = temperature
        self._system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self._user_prompt = user_prompt or self.DEFAULT_USER_PROMPT
        self._batch_size = batch_size
        self._logger = get_logger("tts.sentence_merger")
    
    async def merge(
        self,
        entries: List[SubtitleEntry],
    ) -> List[MergedSubtitleEntry]:
        """
        Merge subtitle entries using AI with automatic batching.
        
        Two-stage approach:
        1. AI determines merge groups (returns only indices)
        2. Local processing merges text based on groups
        
        Args:
            entries: List of subtitle entries to merge
            
        Returns:
            List of merged subtitle entries with original index mapping
        """
        if not entries:
            return []
        
        total_entries = len(entries)
        self._logger.info(f"Starting sentence merge for {total_entries} entries")
        
        try:
            # Determine if batching is needed
            if total_entries <= self._batch_size:
                # Single batch processing
                self._logger.info("Processing in single batch")
                merge_groups = await self._get_merge_groups_single(entries)
            else:
                # Multiple batch processing
                self._logger.info(f"Processing in multiple batches (size={self._batch_size})")
                merge_groups = await self._get_merge_groups_batched(entries)
            
            # Stage 2: Build merged entries from groups
            merged = self._build_merged_entries(merge_groups, entries)
            
            self._logger.info(
                f"Merged {total_entries} entries into {len(merged)} groups"
            )
            return merged
            
        except Exception as e:
            self._logger.error(f"Sentence merge failed: {e}")
            raise SentenceMergeError(f"Failed to merge sentences: {e}")
    
    async def _get_merge_groups_single(
        self,
        entries: List[SubtitleEntry],
    ) -> List[List[int]]:
        """
        Get merge groups for a single batch.
        
        Args:
            entries: List of subtitle entries
            
        Returns:
            List of merge groups, each group is a list of indices
        """
        # Build subtitle text for AI
        subtitles_text = "\n".join(
            f"{i+1}. {entry.text}" for i, entry in enumerate(entries)
        )
        
        user_prompt = self._user_prompt.replace("{subtitles}", subtitles_text)
        
        # Call AI API
        response = await self._call_api(user_prompt)
        
        # Parse groups from response
        groups = self._parse_merge_groups(response, len(entries))
        
        return groups
    
    async def _get_merge_groups_batched(
        self,
        entries: List[SubtitleEntry],
    ) -> List[List[int]]:
        """
        Get merge groups for multiple batches.
        
        Splits entries at punctuation marks to avoid breaking sentences.
        
        Args:
            entries: List of subtitle entries
            
        Returns:
            List of merge groups, each group is a list of indices
        """
        # Split entries into batches at punctuation marks
        batches = self._split_into_batches(entries)
        
        self._logger.info(f"Split into {len(batches)} batches")
        
        all_groups = []
        
        for batch_idx, (start_idx, batch_entries) in enumerate(batches):
            self._logger.info(
                f"Processing batch {batch_idx + 1}/{len(batches)} "
                f"(entries {start_idx} to {start_idx + len(batch_entries) - 1})"
            )
            
            # Get groups for this batch
            batch_groups = await self._get_merge_groups_single(batch_entries)
            
            # Adjust indices to global position
            adjusted_groups = [
                [idx + start_idx for idx in group]
                for group in batch_groups
            ]
            
            all_groups.extend(adjusted_groups)
        
        return all_groups
    
    def _split_into_batches(
        self,
        entries: List[SubtitleEntry],
    ) -> List[tuple[int, List[SubtitleEntry]]]:
        """
        Split entries into batches at punctuation marks.
        
        Args:
            entries: List of subtitle entries
            
        Returns:
            List of (start_index, batch_entries) tuples
        """
        batches = []
        current_start = 0
        
        while current_start < len(entries):
            # Calculate ideal end position
            ideal_end = min(current_start + self._batch_size, len(entries))
            
            # If this is the last batch, take all remaining
            if ideal_end == len(entries):
                batches.append((current_start, entries[current_start:ideal_end]))
                break
            
            # Try to find a punctuation mark near the ideal end
            # Search window: [ideal_end - 100, ideal_end + 100]
            search_start = max(current_start, ideal_end - 100)
            search_end = min(len(entries), ideal_end + 100)
            
            split_point = None
            
            # Look for sentence-ending punctuation
            for i in range(ideal_end, search_end):
                if i >= len(entries):
                    break
                text = entries[i].text.strip()
                if text and text[-1] in '。！？.!?':
                    split_point = i + 1
                    break
            
            # If not found forward, search backward
            if split_point is None:
                for i in range(ideal_end - 1, search_start - 1, -1):
                    if i < current_start:
                        break
                    text = entries[i].text.strip()
                    if text and text[-1] in '。！？.!?':
                        split_point = i + 1
                        break
            
            # If still not found, look for comma
            if split_point is None:
                for i in range(ideal_end, search_end):
                    if i >= len(entries):
                        break
                    text = entries[i].text.strip()
                    if text and text[-1] in '，,':
                        split_point = i + 1
                        break
            
            # If still not found, just split at ideal position
            if split_point is None:
                split_point = ideal_end
            
            batches.append((current_start, entries[current_start:split_point]))
            current_start = split_point
        
        return batches
    
    def _parse_merge_groups(
        self,
        response: str,
        total_entries: int,
    ) -> List[List[int]]:
        """
        Parse AI response into merge groups.
        
        Expected format: "1,2,3|4,5|6|7,8,9"
        
        Args:
            response: AI response string
            total_entries: Total number of entries for validation
            
        Returns:
            List of merge groups, each group is a list of 0-based indices
        """
        groups = []
        covered_indices = set()
        
        # Clean response
        response = response.strip()
        
        # Split by pipe
        group_strs = response.split('|')
        
        for group_str in group_strs:
            group_str = group_str.strip()
            if not group_str:
                continue
            
            try:
                # Parse indices (1-based from AI, convert to 0-based)
                indices = [int(i.strip()) - 1 for i in group_str.split(',')]
                
                # Validate indices
                valid_indices = [i for i in indices if 0 <= i < total_entries]
                
                if not valid_indices:
                    self._logger.warning(f"No valid indices in group: {group_str}")
                    continue
                
                # Check for duplicates
                for idx in valid_indices:
                    if idx in covered_indices:
                        self._logger.warning(f"Duplicate index {idx} in groups")
                    covered_indices.add(idx)
                
                groups.append(sorted(valid_indices))
                
            except (ValueError, AttributeError) as e:
                self._logger.warning(f"Failed to parse group '{group_str}': {e}")
                continue
        
        # Check for missing entries
        all_indices = set(range(total_entries))
        missing_indices = all_indices - covered_indices
        
        if missing_indices:
            self._logger.warning(
                f"AI merge missed {len(missing_indices)} entries, adding as individual groups"
            )
            # Add missing entries as individual groups
            for idx in sorted(missing_indices):
                groups.append([idx])
        
        # Sort groups by first index
        groups.sort(key=lambda g: g[0])
        
        return groups
    
    def _build_merged_entries(
        self,
        merge_groups: List[List[int]],
        original_entries: List[SubtitleEntry],
    ) -> List[MergedSubtitleEntry]:
        """
        Build merged entries from merge groups.
        
        Args:
            merge_groups: List of merge groups (each group is list of indices)
            original_entries: Original subtitle entries
            
        Returns:
            List of merged subtitle entries
        """
        merged = []
        
        for group in merge_groups:
            if not group:
                continue
            
            # Merge text from all entries in group
            merged_text = " ".join(original_entries[i].text for i in group)
            
            # Get time range
            start_time = min(original_entries[i].start_time for i in group)
            end_time = max(original_entries[i].end_time for i in group)
            
            merged.append(MergedSubtitleEntry(
                merged_text=merged_text.strip(),
                original_indices=group,
                start_time=start_time,
                end_time=end_time,
            ))
        
        return merged
    
    async def _call_api(self, user_prompt: str) -> str:
        """Call LLM API for sentence merging."""
        try:
            import httpx
        except ImportError:
            raise SentenceMergeError("httpx is required for AI sentence merging")
        
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": 8192,  # Increased for larger outputs
        }
        
        url = f"{self._base_url}/chat/completions"
        
        self._logger.info(f"Calling AI API for sentence merge: {url}")
        
        async with httpx.AsyncClient(timeout=180.0) as client:  # Increased timeout
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise SentenceMergeError(
                f"AI API error: {response.status_code} - {response.text}"
            )
        
        result = response.json()
        
        if "error" in result:
            error_msg = result.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            raise SentenceMergeError(f"AI API error: {error_msg}")
        
        try:
            content = result["choices"][0]["message"]["content"]
            return content
        except (KeyError, IndexError) as e:
            raise SentenceMergeError(f"Failed to parse AI response: {e}")


# ============================================================================
# Base TTS Engine Interface
# ============================================================================

class BaseTTSEngine(ABC):
    """Abstract base class for TTS engines."""
    
    def __init__(self, config: TTSConfig):
        self._config = config
        self._logger = get_logger(f"tts.{self.__class__.__name__}")
        self._loaded = False
    
    @abstractmethod
    async def load_model(self) -> None:
        """Load TTS model."""
        pass
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize speech from text."""
        pass
    
    @abstractmethod
    def get_sample_rate(self) -> int:
        """Get output sample rate."""
        pass
    
    async def unload_model(self) -> None:
        """Unload model and free memory."""
        self._loaded = False
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded


# ============================================================================
# TTS Engine Implementations
# ============================================================================

class ChatTTSEngine(BaseTTSEngine):
    """ChatTTS engine implementation."""
    
    _model = None  # Singleton model
    _loading = False  # Prevent concurrent loading
    
    async def load_model(self) -> None:
        """Load ChatTTS model in thread pool to avoid blocking."""
        if self._loaded:
            return
        
        # Prevent concurrent loading
        if ChatTTSEngine._loading:
            self._logger.info("ChatTTS is already loading, waiting...")
            while ChatTTSEngine._loading:
                await asyncio.sleep(0.5)
            if ChatTTSEngine._model is not None:
                self._loaded = True
                return
        
        self._logger.info("Loading ChatTTS model...")
        ChatTTSEngine._loading = True
        
        try:
            import ChatTTS
            import torch
            import concurrent.futures
            
            if ChatTTSEngine._model is None:
                device = "cuda" if self._config.use_gpu and torch.cuda.is_available() else "cpu"
                
                # Set model download path to data/models/chattts
                model_dir = Path("data/models/chattts")
                model_dir.mkdir(parents=True, exist_ok=True)
                
                # Run blocking load in thread pool
                def _load_model():
                    chat = ChatTTS.Chat()
                    success = chat.load(
                        compile=False,
                        device=device,
                        custom_path=str(model_dir),
                    )
                    return chat, success
                
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    chat, success = await loop.run_in_executor(executor, _load_model)
                
                if not success:
                    raise EngineLoadError(
                        "ChatTTS model loading failed. "
                        "Please check network connection for model download."
                    )
                
                ChatTTSEngine._model = chat
                self._logger.info(f"ChatTTS loaded on {device}")
            
            self._loaded = True
            
        except ImportError:
            raise EngineLoadError(
                "ChatTTS not installed. Install with: pip install ChatTTS"
            )
        except EngineLoadError:
            raise
        except Exception as e:
            raise EngineLoadError(f"Failed to load ChatTTS: {e}")
        finally:
            ChatTTSEngine._loading = False
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize speech using ChatTTS."""
        if not self._loaded:
            await self.load_model()
        
        # Validate text
        if not text or not text.strip():
            raise SynthesisError("Empty text provided for synthesis")
        
        text = text.strip()
        
        # ChatTTS has issues with very short text, pad if needed
        if len(text) < 5:
            text = text + "。。"
        
        try:
            import torch
            import numpy as np
            
            self._logger.info(f"Synthesizing text ({len(text)} chars): {text[:50]}...")
            
            # Use simpler inference without refine_text to avoid the narrow() error
            # This error often occurs with certain text patterns
            try:
                # Try with skip_refine_text=True to avoid the problematic code path
                wavs = ChatTTSEngine._model.infer(
                    [text],
                    skip_refine_text=True,
                    use_decoder=True,
                )
            except TypeError:
                # Older ChatTTS version without skip_refine_text parameter
                params_infer = ChatTTSEngine._model.InferCodeParams(
                    spk_emb=None,
                    temperature=0.3,
                    top_P=0.7,
                    top_K=20,
                )
                wavs = ChatTTSEngine._model.infer(
                    [text],
                    params_infer_code=params_infer,
                    use_decoder=True,
                )
            
            # Handle generator or list result
            if hasattr(wavs, '__iter__') and not isinstance(wavs, (list, np.ndarray)):
                wavs = list(wavs)
            
            if not wavs or len(wavs) == 0:
                raise SynthesisError("ChatTTS returned empty result")
            
            # Get first audio
            audio_data = wavs[0]
            
            # Convert to numpy if tensor
            if isinstance(audio_data, torch.Tensor):
                audio_data = audio_data.cpu().numpy()
            
            # Flatten if needed
            audio_data = np.array(audio_data).flatten()
            
            if len(audio_data) == 0:
                raise SynthesisError("ChatTTS returned empty audio")
            
            # Normalize to [-1, 1] range
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                audio_data = audio_data / max_val
            
            # Convert to 16-bit PCM
            audio_data = (audio_data * 32767).astype('int16')
            audio_bytes = audio_data.tobytes()
            
            self._logger.info(f"Synthesized {len(audio_bytes)} bytes of audio")
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=24000,
                channels=1,
                sample_width=2,
            )
            
        except SynthesisError:
            raise
        except Exception as e:
            self._logger.error(f"ChatTTS synthesis error for text '{text[:30]}...': {e}")
            raise SynthesisError(f"ChatTTS synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        return 24000


class CoquiTTSEngine(BaseTTSEngine):
    """Coqui TTS engine implementation."""
    
    _model = None
    
    async def load_model(self) -> None:
        """Load Coqui TTS model."""
        if self._loaded:
            return
        
        self._logger.info("Loading Coqui TTS model...")
        
        try:
            from TTS.api import TTS
            import torch
            
            if CoquiTTSEngine._model is None:
                device = "cuda" if self._config.use_gpu and torch.cuda.is_available() else "cpu"
                
                model_name = self._config.model_path or "tts_models/multilingual/multi-dataset/xtts_v2"
                tts = TTS(model_name).to(device)
                
                CoquiTTSEngine._model = tts
                self._logger.info(f"Coqui TTS loaded on {device}")
            
            self._loaded = True
            
        except ImportError:
            raise EngineLoadError("Coqui TTS not installed")
        except Exception as e:
            raise EngineLoadError(f"Failed to load Coqui TTS: {e}")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize speech using Coqui TTS."""
        if not self._loaded:
            await self.load_model()
        
        try:
            import numpy as np
            
            # Coqui TTS synthesis
            wav = CoquiTTSEngine._model.tts(
                text=text,
                speaker=speaker,
                speed=speed,
            )
            
            # Convert to 16-bit PCM
            wav_array = np.array(wav)
            audio_data = (wav_array * 32767).astype('int16')
            audio_bytes = audio_data.tobytes()
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=self.get_sample_rate(),
                channels=1,
                sample_width=2,
            )
            
        except Exception as e:
            raise SynthesisError(f"Coqui TTS synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        return 22050


class VITSEngine(BaseTTSEngine):
    """VITS-based TTS engine (placeholder for various VITS implementations)."""
    
    _model = None
    
    async def load_model(self) -> None:
        """Load VITS model."""
        if self._loaded:
            return
        
        self._logger.info("Loading VITS model...")
        # VITS implementation would go here
        # This is a placeholder that can be extended
        self._loaded = True
        self._logger.warning("VITS engine is a placeholder - implement specific VITS variant")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize speech using VITS."""
        raise SynthesisError("VITS engine not fully implemented - use ChatTTS or Coqui")
    
    def get_sample_rate(self) -> int:
        return 22050


class SparkTTSEngine(BaseTTSEngine):
    """
    SparkTTS engine implementation.
    
    SparkTTS is an open-source TTS from iFlytek with excellent Chinese support.
    GitHub: https://github.com/SparkAudio/Spark-TTS
    
    Requires:
    - spark-tts package installed
    - Optional: reference audio for voice cloning
    """
    
    _model = None
    _reference_audio: Optional[str] = None
    
    async def load_model(self) -> None:
        """Load SparkTTS model."""
        if self._loaded:
            return
        
        self._logger.info("Loading SparkTTS model...")
        
        try:
            from sparktts import SparkTTS as SparkTTSModel
            import torch
            
            if SparkTTSEngine._model is None:
                device = "cuda" if self._config.use_gpu and torch.cuda.is_available() else "cpu"
                
                # Initialize SparkTTS model
                model = SparkTTSModel(
                    model_dir=self._config.model_path,
                    device=device,
                )
                
                SparkTTSEngine._model = model
                self._logger.info(f"SparkTTS loaded on {device}")
            
            self._loaded = True
            
        except ImportError:
            raise EngineLoadError(
                "SparkTTS not installed. Install with: pip install spark-tts"
            )
        except Exception as e:
            raise EngineLoadError(f"Failed to load SparkTTS: {e}")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """
        Synthesize speech using SparkTTS.
        
        Args:
            text: Text to synthesize
            speed: Speech speed multiplier
            speaker: Speaker ID or reference audio path for voice cloning
        """
        if not self._loaded:
            await self.load_model()
        
        try:
            import numpy as np
            
            # speaker can be speaker ID or reference audio path
            reference_audio = speaker or SparkTTSEngine._reference_audio
            
            # Synthesize using SparkTTS
            wav = SparkTTSEngine._model.synthesize(
                text=text,
                speaker=reference_audio,
                speed=speed,
            )
            
            if wav is None or len(wav) == 0:
                raise SynthesisError("SparkTTS returned empty result")
            
            # Convert to numpy array if needed
            if hasattr(wav, 'cpu'):
                wav = wav.cpu().numpy()
            
            wav_array = np.array(wav).flatten()
            
            # Normalize and convert to 16-bit PCM
            if wav_array.max() > 1.0 or wav_array.min() < -1.0:
                wav_array = wav_array / max(abs(wav_array.max()), abs(wav_array.min()))
            
            audio_data = (wav_array * 32767).astype('int16')
            audio_bytes = audio_data.tobytes()
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=self.get_sample_rate(),
                channels=1,
                sample_width=2,
            )
            
        except ImportError as e:
            raise SynthesisError(f"SparkTTS dependency missing: {e}")
        except Exception as e:
            raise SynthesisError(f"SparkTTS synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        # SparkTTS outputs at 16000 Hz
        return 16000
    
    @classmethod
    def set_reference_audio(cls, audio_path: str) -> None:
        """Set default reference audio for voice cloning."""
        cls._reference_audio = audio_path


class IndexTTSEngine(BaseTTSEngine):
    """
    IndexTTS engine implementation.
    
    IndexTTS is a zero-shot voice cloning TTS system.
    GitHub: https://github.com/index-tts/index-tts
    
    Installation:
        git clone https://github.com/index-tts/index-tts
        cd index-tts && pip install -e .
    
    Requires reference audio file for voice cloning.
    """
    
    _model = None
    _reference_audio: Optional[str] = None
    
    async def load_model(self) -> None:
        """Load IndexTTS model."""
        if self._loaded:
            return
        
        self._logger.info("Loading IndexTTS model...")
        
        try:
            # Try multiple import paths for IndexTTS
            try:
                from indextts.infer import IndexTTS as IndexTTSModel
            except ImportError:
                try:
                    from indextts import IndexTTS as IndexTTSModel
                except ImportError:
                    from index_tts import IndexTTS as IndexTTSModel
            
            import torch
            
            if IndexTTSEngine._model is None:
                device = "cuda" if self._config.use_gpu and torch.cuda.is_available() else "cpu"
                
                # Initialize IndexTTS model
                model = IndexTTSModel(
                    model_dir=self._config.model_path,
                    device=device,
                )
                
                IndexTTSEngine._model = model
                self._logger.info(f"IndexTTS loaded on {device}")
            
            self._loaded = True
            
        except ImportError:
            raise EngineLoadError(
                "IndexTTS not installed. Install from: "
                "git clone https://github.com/index-tts/index-tts && cd index-tts && pip install -e ."
            )
        except Exception as e:
            raise EngineLoadError(f"Failed to load IndexTTS: {e}")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """
        Synthesize speech using IndexTTS.
        
        Args:
            text: Text to synthesize
            speed: Speech speed multiplier (not directly supported, use time stretch)
            speaker: Path to reference audio file for voice cloning
        """
        if not self._loaded:
            await self.load_model()
        
        try:
            import numpy as np
            
            # speaker parameter is used as reference audio path
            reference_audio = speaker or IndexTTSEngine._reference_audio
            
            if not reference_audio:
                raise SynthesisError(
                    "IndexTTS requires a reference audio file. "
                    "Set speaker parameter to the path of reference audio."
                )
            
            # Synthesize using IndexTTS
            # IndexTTS.infer returns audio numpy array
            wav = IndexTTSEngine._model.infer(
                text=text,
                reference_audio=reference_audio,
            )
            
            if wav is None or len(wav) == 0:
                raise SynthesisError("IndexTTS returned empty result")
            
            # Convert to numpy array if needed
            if hasattr(wav, 'cpu'):
                wav = wav.cpu().numpy()
            
            wav_array = np.array(wav).flatten()
            
            # Normalize and convert to 16-bit PCM
            if wav_array.max() > 1.0 or wav_array.min() < -1.0:
                wav_array = wav_array / max(abs(wav_array.max()), abs(wav_array.min()))
            
            audio_data = (wav_array * 32767).astype('int16')
            audio_bytes = audio_data.tobytes()
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=self.get_sample_rate(),
                channels=1,
                sample_width=2,
            )
            
        except ImportError as e:
            raise SynthesisError(f"IndexTTS dependency missing: {e}")
        except Exception as e:
            raise SynthesisError(f"IndexTTS synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        # IndexTTS typically outputs at 24000 Hz
        return 24000
    
    @classmethod
    def set_reference_audio(cls, audio_path: str) -> None:
        """Set default reference audio for voice cloning."""
        cls._reference_audio = audio_path


class CozyVoiceEngine(BaseTTSEngine):
    """
    CozyVoice engine implementation.
    
    CozyVoice is an open-source TTS from Alibaba with multi-style support.
    GitHub: https://github.com/FunAudioLLM/CosyVoice
    
    Requires:
    - cosyvoice package installed
    - Optional: reference audio for voice cloning
    """
    
    _model = None
    _reference_audio: Optional[str] = None
    
    async def load_model(self) -> None:
        """Load CozyVoice model."""
        if self._loaded:
            return
        
        self._logger.info("Loading CozyVoice model...")
        
        try:
            from cosyvoice import CosyVoice
            import torch
            
            if CozyVoiceEngine._model is None:
                device = "cuda" if self._config.use_gpu and torch.cuda.is_available() else "cpu"
                
                # Initialize CosyVoice model
                # Default to CosyVoice-300M-SFT model
                model_path = self._config.model_path or "CosyVoice-300M-SFT"
                model = CosyVoice(model_path, device=device)
                
                CozyVoiceEngine._model = model
                self._logger.info(f"CozyVoice loaded on {device}")
            
            self._loaded = True
            
        except ImportError:
            raise EngineLoadError(
                "CosyVoice not installed. See: https://github.com/FunAudioLLM/CosyVoice"
            )
        except Exception as e:
            raise EngineLoadError(f"Failed to load CozyVoice: {e}")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """
        Synthesize speech using CozyVoice.
        
        Args:
            text: Text to synthesize
            speed: Speech speed multiplier (applied via time stretch)
            speaker: Speaker name or reference audio path for voice cloning
        """
        if not self._loaded:
            await self.load_model()
        
        try:
            import numpy as np
            
            # speaker can be speaker name or reference audio path
            reference = speaker or CozyVoiceEngine._reference_audio
            
            # Determine synthesis mode based on reference
            if reference and Path(reference).exists():
                # Zero-shot voice cloning mode
                wav_generator = CozyVoiceEngine._model.inference_zero_shot(
                    text,
                    prompt_text="",  # Optional prompt text
                    prompt_speech_16k=reference,
                )
            elif reference:
                # SFT mode with speaker name
                wav_generator = CozyVoiceEngine._model.inference_sft(
                    text,
                    speaker=reference,
                )
            else:
                # Default SFT mode
                wav_generator = CozyVoiceEngine._model.inference_sft(
                    text,
                    speaker="中文女",  # Default Chinese female speaker
                )
            
            # CosyVoice returns a generator, collect all chunks
            wav_chunks = []
            for chunk in wav_generator:
                if 'tts_speech' in chunk:
                    wav_chunks.append(chunk['tts_speech'])
            
            if not wav_chunks:
                raise SynthesisError("CozyVoice returned empty result")
            
            # Concatenate all chunks
            wav = np.concatenate(wav_chunks)
            
            # Convert to numpy array if needed
            if hasattr(wav, 'cpu'):
                wav = wav.cpu().numpy()
            
            wav_array = np.array(wav).flatten()
            
            # Normalize and convert to 16-bit PCM
            if wav_array.max() > 1.0 or wav_array.min() < -1.0:
                wav_array = wav_array / max(abs(wav_array.max()), abs(wav_array.min()))
            
            audio_data = (wav_array * 32767).astype('int16')
            audio_bytes = audio_data.tobytes()
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=self.get_sample_rate(),
                channels=1,
                sample_width=2,
            )
            
        except ImportError as e:
            raise SynthesisError(f"CozyVoice dependency missing: {e}")
        except Exception as e:
            raise SynthesisError(f"CozyVoice synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        # CosyVoice outputs at 22050 Hz
        return 22050
    
    @classmethod
    def set_reference_audio(cls, audio_path: str) -> None:
        """Set default reference audio for voice cloning."""
        cls._reference_audio = audio_path


# ============================================================================
# API-based TTS Engines
# ============================================================================

class APIBasedTTSEngine(BaseTTSEngine):
    """
    Base class for API-based TTS engines.
    
    Supports calling remote TTS services via HTTP API.
    """
    
    def __init__(self, config: TTSConfig, api_url: str):
        super().__init__(config)
        self._api_url = api_url.rstrip('/') if api_url else ""
    
    async def load_model(self) -> None:
        """API mode doesn't need to load model locally."""
        if not self._api_url:
            raise EngineLoadError("API URL not configured")
        self._loaded = True
        self._logger.info(f"API mode enabled, endpoint: {self._api_url}")
    
    async def _call_api(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Call TTS API and return audio bytes."""
        try:
            import httpx
        except ImportError:
            raise SynthesisError("httpx is required for API mode")
        
        payload = {
            "text": text,
            "speed": speed,
        }
        if speaker:
            payload["speaker"] = speaker
        payload.update(kwargs)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._api_url}/synthesize",
                json=payload,
            )
            
            if response.status_code != 200:
                raise SynthesisError(f"API error: {response.status_code} - {response.text}")
            
            # Check if response is JSON with audio data or raw audio
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data = response.json()
                if "audio" in data:
                    import base64
                    return base64.b64decode(data["audio"])
                raise SynthesisError("API response missing audio data")
            else:
                return response.content


class IndexTTSAPIEngine(APIBasedTTSEngine):
    """IndexTTS API mode engine."""
    
    def __init__(self, config: TTSConfig):
        super().__init__(config, config.indextts_api_url or "")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize using IndexTTS API."""
        if not self._loaded:
            await self.load_model()
        
        try:
            # Use reference audio from config or speaker parameter
            reference = speaker or self._config.reference_audio
            
            audio_bytes = await self._call_api(
                text=text,
                speed=speed,
                reference_audio=reference,
            )
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=self.get_sample_rate(),
                channels=1,
                sample_width=2,
            )
        except Exception as e:
            raise SynthesisError(f"IndexTTS API synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        return 24000


class SparkTTSAPIEngine(APIBasedTTSEngine):
    """SparkTTS API mode engine."""
    
    def __init__(self, config: TTSConfig):
        super().__init__(config, config.sparktts_api_url or "")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize using SparkTTS API."""
        if not self._loaded:
            await self.load_model()
        
        try:
            reference = speaker or self._config.reference_audio
            
            audio_bytes = await self._call_api(
                text=text,
                speed=speed,
                speaker=reference,
            )
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=self.get_sample_rate(),
                channels=1,
                sample_width=2,
            )
        except Exception as e:
            raise SynthesisError(f"SparkTTS API synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        return 16000


class CozyVoiceAPIEngine(APIBasedTTSEngine):
    """CozyVoice API mode engine."""
    
    def __init__(self, config: TTSConfig):
        super().__init__(config, config.cozyvoice_api_url or "")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize using CozyVoice API."""
        if not self._loaded:
            await self.load_model()
        
        try:
            # Use speaker from parameter, config, or default
            spk = speaker or self._config.cozyvoice_speaker or "中文女"
            reference = self._config.reference_audio
            
            audio_bytes = await self._call_api(
                text=text,
                speed=speed,
                speaker=spk,
                reference_audio=reference,
            )
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=self.get_sample_rate(),
                channels=1,
                sample_width=2,
            )
        except Exception as e:
            raise SynthesisError(f"CozyVoice API synthesis failed: {e}")
    
    def get_sample_rate(self) -> int:
        return 22050


# ============================================================================
# Online TTS Engines (Azure TTS, Edge TTS, Volc TTS)
# ============================================================================

class AzureTTSEngine(BaseTTSEngine):
    """
    Azure TTS engine implementation.
    
    Uses Microsoft Translator's TTS endpoint (free tier).
    Supports multiple voices with emotion/style control.
    """
    
    _endpoint = None
    _expired_at = None
    
    # Constants from reference implementation
    ENDPOINT_URL = "https://dev.microsofttranslator.com/apps/endpoint?api-version=1.0"
    USER_AGENT = "okhttp/4.5.0"
    CLIENT_VERSION = "4.0.530a 5fe1dc6c"
    USER_ID = "0f04d16a175c411e"
    HOME_GEOGRAPHIC_REGION = "zh-Hans-CN"
    CLIENT_TRACE_ID = "aab069b9-70a7-4844-a734-96cd78d94be9"
    VOICE_DECODE_KEY = "oik6PdDdMnOXemTbwvMn9de/h9lFnfBaCWbGMMZqqoSaQaqUOqjVGm5NqsmjcBI1x+sS9ugjB55HEJWRiFXYFw=="
    
    async def load_model(self) -> None:
        """Azure TTS doesn't need local model loading."""
        self._loaded = True
        self._logger.info("Azure TTS engine ready (online service)")
    
    def _sign(self, url_str: str) -> str:
        """Generate signature for Azure endpoint request."""
        import base64
        import hashlib
        import hmac
        import uuid
        from datetime import datetime
        from urllib.parse import quote
        
        u = url_str.split("://")[1]
        encoded_url = quote(u, safe='')
        uuid_str = str(uuid.uuid4()).replace("-", "")
        formatted_date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S").lower() + "gmt"
        bytes_to_sign = f"MSTranslatorAndroidApp{encoded_url}{formatted_date}{uuid_str}".lower().encode('utf-8')
        
        decode = base64.b64decode(self.VOICE_DECODE_KEY)
        hmac_sha256 = hmac.new(decode, bytes_to_sign, hashlib.sha256)
        secret_key = hmac_sha256.digest()
        sign_base64 = base64.b64encode(secret_key).decode()
        
        return f"MSTranslatorAndroidApp::{sign_base64}::{formatted_date}::{uuid_str}"
    
    async def _get_endpoint(self) -> dict:
        """Get Azure TTS endpoint with authentication."""
        import time
        import json
        import base64
        
        current_time = int(time.time())
        
        # Check if cached endpoint is still valid
        if AzureTTSEngine._endpoint and AzureTTSEngine._expired_at:
            if current_time < AzureTTSEngine._expired_at - 60:
                return AzureTTSEngine._endpoint
        
        try:
            import httpx
        except ImportError:
            raise SynthesisError("httpx is required for Azure TTS")
        
        signature = self._sign(self.ENDPOINT_URL)
        headers = {
            "Accept-Language": "zh-Hans",
            "X-ClientVersion": self.CLIENT_VERSION,
            "X-UserId": self.USER_ID,
            "X-HomeGeographicRegion": self.HOME_GEOGRAPHIC_REGION,
            "X-ClientTraceId": self.CLIENT_TRACE_ID,
            "X-MT-Signature": signature,
            "User-Agent": self.USER_AGENT,
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": "0",
            "Accept-Encoding": "gzip",
        }
        
        async with httpx.AsyncClient(timeout=30.0, proxy=self._config.proxy_url) as client:
            response = await client.post(self.ENDPOINT_URL, headers=headers)
            response.raise_for_status()
            endpoint = response.json()
        
        # Parse JWT to get expiration time
        jwt = endpoint['t'].split('.')[1]
        # Add padding if needed
        padding = 4 - len(jwt) % 4
        if padding != 4:
            jwt += '=' * padding
        decoded_jwt = json.loads(base64.b64decode(jwt).decode('utf-8'))
        AzureTTSEngine._expired_at = decoded_jwt['exp']
        AzureTTSEngine._endpoint = endpoint
        
        return endpoint
    
    def _build_ssml(self, text: str, voice_name: str, rate: str, pitch: str, style: str) -> str:
        """Build SSML for Azure TTS."""
        return f"""
<speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" version="1.0" xml:lang="zh-CN">
<voice name="{voice_name}">
    <mstts:express-as style="{style}" styledegree="1.0" role="default">
        <prosody rate="{rate}%" pitch="{pitch}%">
            {text}
        </prosody>
    </mstts:express-as>
</voice>
</speak>
        """
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize speech using Azure TTS."""
        if not self._loaded:
            await self.load_model()
        
        try:
            import httpx
        except ImportError:
            raise SynthesisError("httpx is required for Azure TTS")
        
        try:
            # Get endpoint
            endpoint = await self._get_endpoint()
            
            # Use config values or defaults
            voice_name = speaker or self._config.azure_tts_voice
            style = self._config.azure_tts_style
            rate = self._config.azure_tts_rate
            pitch = self._config.azure_tts_pitch
            
            # Adjust rate based on speed parameter
            if speed != 1.0:
                rate_adjustment = int((speed - 1.0) * 100)
                rate = str(rate_adjustment)
            
            url = f"https://{endpoint['r']}.tts.speech.microsoft.com/cognitiveservices/v1"
            headers = {
                "Authorization": endpoint["t"],
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            }
            
            ssml = self._build_ssml(text, voice_name, rate, pitch, style)
            
            async with httpx.AsyncClient(timeout=60.0, proxy=self._config.proxy_url) as client:
                response = await client.post(url, headers=headers, content=ssml.encode())
                response.raise_for_status()
                audio_data = response.content
            
            # Convert MP3 to PCM using ffmpeg
            audio_segment = await self._convert_mp3_to_pcm(audio_data)
            
            return audio_segment
            
        except Exception as e:
            self._logger.error(f"Azure TTS synthesis error: {e}")
            raise SynthesisError(f"Azure TTS synthesis failed: {e}")
    
    async def _convert_mp3_to_pcm(self, mp3_data: bytes) -> AudioSegment:
        """Convert MP3 audio to PCM using ffmpeg."""
        import subprocess
        import tempfile
        import os
        
        # Write MP3 to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(mp3_data)
            mp3_path = f.name
        
        wav_path = mp3_path.replace('.mp3', '.wav')
        
        try:
            # Convert to WAV using ffmpeg
            cmd = [
                self._config.ffmpeg_path,
                '-i', mp3_path,
                '-ar', '24000',
                '-ac', '1',
                '-f', 'wav',
                '-y',
                wav_path
            ]
            
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True
            )
            
            if result.returncode != 0:
                raise SynthesisError(f"FFmpeg conversion failed: {result.stderr.decode()}")
            
            # Read WAV file
            import wave
            with wave.open(wav_path, 'rb') as wav_file:
                audio_bytes = wav_file.readframes(wav_file.getnframes())
                sample_rate = wav_file.getframerate()
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=sample_rate,
                channels=1,
                sample_width=2,
            )
        finally:
            # Cleanup temp files
            if os.path.exists(mp3_path):
                os.unlink(mp3_path)
            if os.path.exists(wav_path):
                os.unlink(wav_path)
    
    def get_sample_rate(self) -> int:
        return 24000


class EdgeTTSEngine(BaseTTSEngine):
    """
    Edge TTS engine implementation.
    
    Uses Microsoft Edge's free TTS service via edge-tts library.
    Supports multiple voices with rate and pitch control.
    """
    
    async def load_model(self) -> None:
        """Edge TTS doesn't need local model loading."""
        try:
            import edge_tts
            self._loaded = True
            self._logger.info("Edge TTS engine ready (online service)")
        except ImportError:
            raise EngineLoadError(
                "edge-tts not installed. Install with: pip install edge-tts"
            )
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize speech using Edge TTS."""
        if not self._loaded:
            await self.load_model()
        
        try:
            import edge_tts
            import tempfile
            import os
            
            # Validate text - Edge TTS requires meaningful text
            text_stripped = text.strip()
            if not text_stripped or len(text_stripped) < 2:
                self._logger.warning(f"Skipping synthesis for too short text: '{text}' (len={len(text_stripped)})")
                # Return silent audio segment
                import numpy as np
                silent_duration = 0.5  # 0.5 seconds of silence
                sample_rate = 24000
                num_samples = int(silent_duration * sample_rate)
                silent_audio = np.zeros(num_samples * 2, dtype=np.int16)  # 16-bit PCM
                return AudioSegment(
                    data=silent_audio.tobytes(),
                    sample_rate=sample_rate,
                    channels=1,
                    sample_width=2,
                )
            
            # Use config values or defaults
            voice = speaker or self._config.edge_tts_voice
            rate = self._config.edge_tts_rate
            pitch = self._config.edge_tts_pitch
            
            # Log parameters for debugging
            self._logger.info(f"Edge TTS params: voice={voice}, rate={rate}, pitch={pitch}, text_len={len(text)}")
            
            # Validate voice parameter
            if not voice:
                raise SynthesisError("Edge TTS voice parameter is required but not set")
            
            # Adjust rate based on speed parameter
            if speed != 1.0:
                rate_percent = int((speed - 1.0) * 100)
                rate = f"{'+' if rate_percent >= 0 else ''}{rate_percent}%"
            
            # Create communicate object
            communicate = edge_tts.Communicate(
                text_stripped,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                temp_path = f.name
            
            try:
                await communicate.save(temp_path)
                
                # Convert MP3 to PCM
                audio_segment = await self._convert_mp3_to_pcm(temp_path)
                return audio_segment
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
        except Exception as e:
            self._logger.error(f"Edge TTS synthesis error: {e}")
            raise SynthesisError(f"Edge TTS synthesis failed: {e}")
    
    async def _convert_mp3_to_pcm(self, mp3_path: str) -> AudioSegment:
        """Convert MP3 file to PCM using ffmpeg."""
        import subprocess
        import os
        
        wav_path = mp3_path.replace('.mp3', '.wav')
        
        try:
            cmd = [
                self._config.ffmpeg_path,
                '-i', mp3_path,
                '-ar', '24000',
                '-ac', '1',
                '-f', 'wav',
                '-y',
                wav_path
            ]
            
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True
            )
            
            if result.returncode != 0:
                raise SynthesisError(f"FFmpeg conversion failed: {result.stderr.decode()}")
            
            # Read WAV file
            import wave
            with wave.open(wav_path, 'rb') as wav_file:
                audio_bytes = wav_file.readframes(wav_file.getnframes())
                sample_rate = wav_file.getframerate()
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=sample_rate,
                channels=1,
                sample_width=2,
            )
        finally:
            if os.path.exists(wav_path):
                os.unlink(wav_path)
    
    def get_sample_rate(self) -> int:
        return 24000


class VolcTTSEngine(BaseTTSEngine):
    """
    Volc (火山) TTS engine implementation.
    
    Uses Volcengine's free TTS service.
    Supports multiple Chinese voices.
    """
    
    async def load_model(self) -> None:
        """Volc TTS doesn't need local model loading."""
        self._loaded = True
        self._logger.info("Volc TTS engine ready (online service)")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize speech using Volc TTS."""
        if not self._loaded:
            await self.load_model()
        
        try:
            import httpx
            import base64
        except ImportError:
            raise SynthesisError("httpx is required for Volc TTS")
        
        try:
            # Use config values or defaults
            voice = speaker or self._config.volc_tts_voice
            
            headers = {
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,zh-TW;q=0.6",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Origin": "chrome-extension://klgfhbiooeogdfodpopgppeadghjjemk",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "none",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json",
            }
            
            # Detect language
            language = None
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(
                        "https://translate.volcengine.com/web/langdetect/v1/",
                        headers=headers,
                        json={"text": text},
                    )
                    if response.status_code == 200:
                        language = response.json().get("language")
                except Exception:
                    pass  # Language detection is optional
            
            # Build request payload
            json_data = {
                "text": text,
                "speaker": voice,
            }
            if language:
                json_data["language"] = language
            
            # Call TTS API
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://translate.volcengine.com/crx/tts/v1/",
                    headers=headers,
                    json=json_data,
                )
                response.raise_for_status()
            
            resp = response.json()
            audio = resp.get("audio")
            if audio is None:
                self._logger.error(f"Volc TTS response: {resp}")
                raise SynthesisError(f"Volc TTS {voice} failed to generate audio")
            
            audio_data = audio.get("data")
            if audio_data is None:
                self._logger.error(f"Volc TTS response: {resp}")
                raise SynthesisError(f"Volc TTS {voice} returned empty audio data")
            
            # Decode base64 audio (MP3 format)
            mp3_bytes = base64.b64decode(audio_data)
            
            # Convert MP3 to PCM
            audio_segment = await self._convert_mp3_to_pcm(mp3_bytes)
            
            return audio_segment
            
        except SynthesisError:
            raise
        except Exception as e:
            self._logger.error(f"Volc TTS synthesis error: {e}")
            raise SynthesisError(f"Volc TTS synthesis failed: {e}")
    
    async def _convert_mp3_to_pcm(self, mp3_data: bytes) -> AudioSegment:
        """Convert MP3 audio to PCM using ffmpeg."""
        import subprocess
        import tempfile
        import os
        
        # Write MP3 to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(mp3_data)
            mp3_path = f.name
        
        wav_path = mp3_path.replace('.mp3', '.wav')
        
        try:
            cmd = [
                self._config.ffmpeg_path,
                '-i', mp3_path,
                '-ar', '24000',
                '-ac', '1',
                '-f', 'wav',
                '-y',
                wav_path
            ]
            
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True
            )
            
            if result.returncode != 0:
                raise SynthesisError(f"FFmpeg conversion failed: {result.stderr.decode()}")
            
            # Read WAV file
            import wave
            with wave.open(wav_path, 'rb') as wav_file:
                audio_bytes = wav_file.readframes(wav_file.getnframes())
                sample_rate = wav_file.getframerate()
            
            return AudioSegment(
                data=audio_bytes,
                sample_rate=sample_rate,
                channels=1,
                sample_width=2,
            )
        finally:
            if os.path.exists(mp3_path):
                os.unlink(mp3_path)
            if os.path.exists(wav_path):
                os.unlink(wav_path)
    
    def get_sample_rate(self) -> int:
        return 24000


# ============================================================================
# Engine Factory
# ============================================================================

def create_engine(config: TTSConfig) -> BaseTTSEngine:
    """Factory function to create TTS engine based on config."""
    
    # Check for API mode for supported engines
    if config.engine == TTSEngine.INDEXTTS and config.indextts_mode == "api":
        return IndexTTSAPIEngine(config)
    
    if config.engine == TTSEngine.SPARKTTS and config.sparktts_mode == "api":
        return SparkTTSAPIEngine(config)
    
    if config.engine == TTSEngine.COZYVOICE and config.cozyvoice_mode == "api":
        return CozyVoiceAPIEngine(config)
    
    # Online TTS engines
    if config.engine == TTSEngine.AZURE_TTS:
        return AzureTTSEngine(config)
    
    if config.engine == TTSEngine.EDGE_TTS:
        return EdgeTTSEngine(config)
    
    if config.engine == TTSEngine.VOLC_TTS:
        return VolcTTSEngine(config)
    
    # Local mode engines
    engines = {
        TTSEngine.CHATTTS: ChatTTSEngine,
        TTSEngine.COQUI: CoquiTTSEngine,
        TTSEngine.VITS: VITSEngine,
        TTSEngine.SPARKTTS: SparkTTSEngine,
        TTSEngine.INDEXTTS: IndexTTSEngine,
        TTSEngine.COZYVOICE: CozyVoiceEngine,
    }
    
    engine_class = engines.get(config.engine)
    if not engine_class:
        raise EngineLoadError(f"Unknown TTS engine: {config.engine}")
    
    return engine_class(config)


# ============================================================================
# Speed Calculator
# ============================================================================

class SpeedCalculator:
    """Calculates optimal speech speed for subtitles."""
    
    def __init__(
        self,
        base_chars_per_second: float = 4.0,
        min_speed: float = 0.5,
        max_speed: float = 2.0,
    ):
        self._base_cps = base_chars_per_second
        self._min_speed = min_speed
        self._max_speed = max_speed
    
    def calculate(self, text: str, available_duration: float) -> float:
        """
        Calculate optimal speed for text to fit in duration.
        
        Args:
            text: Text to synthesize
            available_duration: Available time in seconds
            
        Returns:
            Speed multiplier (1.0 = normal)
        """
        if available_duration <= 0:
            return 1.0
        
        # Calculate natural duration at base speed
        char_count = len(text)
        natural_duration = char_count / self._base_cps
        
        if natural_duration <= 0:
            return 1.0
        
        # Calculate required speed
        speed = natural_duration / available_duration
        
        # Clamp to valid range
        return max(self._min_speed, min(self._max_speed, speed))


# ============================================================================
# Text Splitter
# ============================================================================

class TextSplitter:
    """Splits long text into TTS-friendly segments."""
    
    def __init__(self, max_chars: int = 100):
        self._max_chars = max_chars
    
    def split(self, text: str) -> List[str]:
        """Split text into segments."""
        if len(text) <= self._max_chars:
            return [text]
        
        segments = []
        remaining = text
        
        while remaining:
            if len(remaining) <= self._max_chars:
                segments.append(remaining)
                break
            
            # Find best split point
            split_pos = self._find_split_point(remaining)
            segments.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
        
        return [s for s in segments if s]
    
    def _find_split_point(self, text: str) -> int:
        """Find optimal split point in text."""
        # Look for punctuation within max_chars
        for i in range(min(len(text), self._max_chars) - 1, 0, -1):
            if text[i] in SPLIT_PUNCTUATION:
                return i + 1
        
        # No punctuation found, split at max_chars
        return self._max_chars


# ============================================================================
# Audio Processor
# ============================================================================

class AudioProcessor:
    """Handles audio processing operations."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self._ffmpeg = ffmpeg_path
        self._logger = get_logger("tts.audio")
    
    def concatenate_with_timing(
        self,
        segments: List[Tuple[float, AudioSegment]],
        total_duration: float,
        sample_rate: int,
    ) -> bytes:
        """
        Concatenate audio segments at specified times.
        
        Args:
            segments: List of (start_time, audio_segment) tuples
            total_duration: Total output duration in seconds
            sample_rate: Output sample rate
            
        Returns:
            Combined audio data as bytes
        """
        # Create silent audio buffer
        total_samples = int(total_duration * sample_rate)
        output = bytearray(total_samples * 2)  # 16-bit = 2 bytes per sample
        
        for start_time, segment in segments:
            start_sample = int(start_time * sample_rate)
            
            # Resample if needed
            if segment.sample_rate != sample_rate:
                segment = self._resample(segment, sample_rate)
            
            # Copy audio data to output buffer
            end_sample = min(start_sample + len(segment.data) // 2, total_samples)
            copy_bytes = (end_sample - start_sample) * 2
            
            if copy_bytes > 0 and start_sample < total_samples:
                output[start_sample * 2:start_sample * 2 + copy_bytes] = segment.data[:copy_bytes]
        
        return bytes(output)
    
    def _resample(self, segment: AudioSegment, target_rate: int) -> AudioSegment:
        """Resample audio to target sample rate (simple linear interpolation)."""
        if segment.sample_rate == target_rate:
            return segment
        
        # Simple resampling - for production use librosa or scipy
        ratio = target_rate / segment.sample_rate
        old_samples = len(segment.data) // 2
        new_samples = int(old_samples * ratio)
        
        # Unpack old samples
        old_data = struct.unpack(f'{old_samples}h', segment.data)
        
        # Linear interpolation
        new_data = []
        for i in range(new_samples):
            old_pos = i / ratio
            old_idx = int(old_pos)
            frac = old_pos - old_idx
            
            if old_idx + 1 < old_samples:
                sample = int(old_data[old_idx] * (1 - frac) + old_data[old_idx + 1] * frac)
            else:
                sample = old_data[min(old_idx, old_samples - 1)]
            
            new_data.append(max(-32768, min(32767, sample)))
        
        return AudioSegment(
            data=struct.pack(f'{len(new_data)}h', *new_data),
            sample_rate=target_rate,
            channels=segment.channels,
            sample_width=segment.sample_width,
        )

    async def save_audio(
        self,
        audio_data: bytes,
        sample_rate: int,
        output_path: Path,
        output_format: OutputFormat,
        bitrate: str = "128k",
    ) -> None:
        """Save audio data to file with format conversion."""
        # First save as WAV
        wav_path = output_path.with_suffix(".wav")
        
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        # Convert if needed
        if output_format != OutputFormat.WAV:
            await self._convert_audio(wav_path, output_path, output_format, bitrate)
            wav_path.unlink()  # Remove temp WAV
        else:
            wav_path.rename(output_path)
    
    async def _convert_audio(
        self,
        input_path: Path,
        output_path: Path,
        output_format: OutputFormat,
        bitrate: str,
    ) -> None:
        """Convert audio using FFmpeg."""
        codec_map = {
            OutputFormat.M4A: ["-c:a", "aac", "-b:a", bitrate],
            OutputFormat.MP3: ["-c:a", "libmp3lame", "-b:a", bitrate],
        }
        
        codec_args = codec_map.get(output_format, [])
        
        cmd = [
            self._ffmpeg,
            "-i", str(input_path),
            *codec_args,
            "-y",
            str(output_path),
        ]
        
        # Use subprocess.run in thread pool for Windows compatibility
        # asyncio.create_subprocess_exec raises NotImplementedError on Windows
        def run_ffmpeg():
            result = subprocess.run(
                cmd,
                capture_output=True,
            )
            return result
        
        result = await asyncio.to_thread(run_ffmpeg)
        
        if result.returncode != 0:
            raise AudioProcessError(f"FFmpeg conversion failed: {result.stderr.decode()}")


# ============================================================================
# TTS Service
# ============================================================================

class TTSService(BaseService):
    """
    Text-to-Speech service.
    
    Implements BaseService interface for worker integration.
    Supports multiple TTS engines with speed calculation.
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize TTS service.
        
        Args:
            config: TTS configuration
        """
        self._config = config or TTSConfig()
        self._logger = get_logger("tts")
        self._srt_parser = TTSSRTParser()
        self._speed_calc = SpeedCalculator(
            base_chars_per_second=self._config.base_chars_per_second,
            min_speed=self._config.min_speed,
            max_speed=self._config.max_speed,
        )
        self._text_splitter = TextSplitter(self._config.max_chars_per_segment)
        self._audio_processor = AudioProcessor(self._config.ffmpeg_path)
        self._engine: Optional[BaseTTSEngine] = None
        self._current_task_id: Optional[str] = None
        self._cancelled = False

    async def execute(
        self,
        task: Task,
        progress_callback: ProgressCallback,
        payload_callback=None,
    ) -> Dict[str, Any]:
        """
        Execute TTS task.
        
        Args:
            task: TTS task
            progress_callback: Progress callback
            payload_callback: Optional callback to update task payload (unused)
            
        Returns:
            TTS result
        """
        self._current_task_id = task.id
        self._cancelled = False
        payload = task.payload or {}
        
        video_id = payload.get("video_id")
        subtitle_path = payload.get("subtitle_path")
        
        if not subtitle_path:
            raise TTSError("subtitle_path is required")
        
        subtitle_path = Path(subtitle_path)
        if not subtitle_path.exists():
            raise TTSError(f"Subtitle file not found: {subtitle_path}")
        
        # Always use service config (loaded from DB in main.py) for engine
        # But allow payload to override engine selection for task-specific choice
        engine_name = TTSEngine(payload.get("engine")) if payload.get("engine") else self._config.engine
        speaker = payload.get("speaker") or self._config.speaker
        output_format = OutputFormat(payload.get("output_format") or self._config.output_format.value)
        
        # Override engine in config for create_engine to use correct settings
        self._config.engine = engine_name
        
        # Override online TTS voice settings from payload if provided
        # This allows task-specific voice selection
        if payload.get("edge_tts_voice"):
            self._config.edge_tts_voice = payload["edge_tts_voice"]
        if payload.get("azure_tts_voice"):
            self._config.azure_tts_voice = payload["azure_tts_voice"]
        if payload.get("volc_tts_voice"):
            self._config.volc_tts_voice = payload["volc_tts_voice"]
        
        output_path = subtitle_path.parent / f"audio_tts.{output_format.value}"
        
        # Sentence merge config from payload or service config
        enable_merge = payload.get("enable_sentence_merge", self._config.enable_sentence_merge)
        skip_ai_merge = payload.get("skip_ai_merge", False)  # Skip AI merge if user provided entries
        user_merged_entries = payload.get("merged_entries")  # User-adjusted merged entries
        merge_api_key = payload.get("sentence_merge_api_key")
        merge_base_url = payload.get("sentence_merge_base_url")
        merge_model = payload.get("sentence_merge_model", self._config.sentence_merge_model)
        merge_temperature = payload.get("sentence_merge_temperature", self._config.sentence_merge_temperature)
        merge_system_prompt = payload.get("sentence_merge_system_prompt", self._config.sentence_merge_system_prompt)
        merge_user_prompt = payload.get("sentence_merge_user_prompt", self._config.sentence_merge_user_prompt)
        
        try:
            # Parse subtitles
            progress_callback(0)
            self._logger.info(f"Parsing subtitles: {subtitle_path}")
            entries = self._srt_parser.parse(subtitle_path)
            
            if not entries:
                raise TTSError("No subtitle entries found")
            
            total_entries = len(entries)
            self._logger.info(f"Found {total_entries} subtitle entries")
            
            # Sentence merge (if enabled and API configured)
            merged_entries: Optional[List[MergedSubtitleEntry]] = None
            
            # Check if user provided pre-adjusted merged entries
            if skip_ai_merge and user_merged_entries:
                self._logger.info("Using user-provided merged entries (skipping AI merge)")
                # Convert user entries to MergedSubtitleEntry objects
                merged_entries = [
                    MergedSubtitleEntry(
                        merged_text=e.get("merged_text", ""),
                        original_indices=e.get("original_indices", []),
                        start_time=e.get("start_time", 0),
                        end_time=e.get("end_time", 0),
                    )
                    for e in user_merged_entries
                ]
                self._logger.info(f"Loaded {len(merged_entries)} user-adjusted merged entries")
            elif enable_merge and merge_api_key and merge_base_url:
                progress_callback(2)
                self._logger.info("Performing AI sentence merge...")
                
                try:
                    merger = SentenceMerger(
                        api_key=merge_api_key,
                        base_url=merge_base_url,
                        model=merge_model,
                        temperature=merge_temperature,
                        system_prompt=merge_system_prompt,
                        user_prompt=merge_user_prompt,
                    )
                    merged_entries = await merger.merge(entries)
                    self._logger.info(
                        f"Sentence merge: {total_entries} -> {len(merged_entries)} groups"
                    )
                except SentenceMergeError as e:
                    self._logger.warning(f"Sentence merge failed, continuing without merge: {e}")
                    merged_entries = None
            
            # Load TTS engine
            progress_callback(5)
            self._logger.info(f"Loading TTS engine: {engine_name.value}")
            
            # Use self._config directly to preserve all engine-specific settings
            # (e.g., edge_tts_voice, azure_tts_voice, etc.)
            self._engine = create_engine(self._config)
            await self._engine.load_model()
            
            sample_rate = self._engine.get_sample_rate()
            
            # Synthesize based on merged or original entries
            segments: List[Tuple[float, AudioSegment]] = []
            
            if merged_entries:
                # Use merged entries for synthesis
                total_items = len(merged_entries)
                for i, merged in enumerate(merged_entries):
                    if self._cancelled:
                        raise TTSError("TTS cancelled")
                    
                    # Calculate speed based on merged time range
                    duration = merged.end_time - merged.start_time
                    speed = self._speed_calc.calculate(merged.merged_text, duration)
                    
                    # Split long text
                    text_parts = self._text_splitter.split(merged.merged_text)
                    
                    # Synthesize parts
                    part_segments = []
                    for part in text_parts:
                        audio = await self._engine.synthesize(part, speed, speaker)
                        part_segments.append(audio)
                    
                    # Combine parts
                    if len(part_segments) == 1:
                        combined = part_segments[0]
                    else:
                        combined = self._combine_segments(part_segments)
                    
                    segments.append((merged.start_time, combined))
                    
                    # Update progress (5-95%)
                    progress = 5 + int((i + 1) / total_items * 90)
                    progress_callback(progress)
                    
                    self._logger.debug(
                        f"Synthesized merged entry {i + 1}/{total_items} "
                        f"(original indices: {merged.original_indices})"
                    )
            else:
                # Use original entries
                for i, entry in enumerate(entries):
                    if self._cancelled:
                        raise TTSError("TTS cancelled")
                    
                    # Calculate speed
                    speed = self._speed_calc.calculate(entry.text, entry.duration)
                    
                    # Split long text
                    text_parts = self._text_splitter.split(entry.text)
                    
                    # Synthesize parts
                    part_segments = []
                    for part in text_parts:
                        audio = await self._engine.synthesize(part, speed, speaker)
                        part_segments.append(audio)
                    
                    # Combine parts
                    if len(part_segments) == 1:
                        combined = part_segments[0]
                    else:
                        combined = self._combine_segments(part_segments)
                    
                    segments.append((entry.start_time, combined))
                    
                    # Update progress (5-95%)
                    progress = 5 + int((i + 1) / total_entries * 90)
                    progress_callback(progress)
                    
                    self._logger.debug(f"Synthesized entry {i + 1}/{total_entries}")
            
            # Calculate total duration
            total_duration = max(e.end_time for e in entries) + 1.0
            
            # Concatenate all segments
            progress_callback(95)
            self._logger.info("Concatenating audio segments...")
            
            audio_data = self._audio_processor.concatenate_with_timing(
                segments, total_duration, sample_rate
            )
            
            # Save output
            self._logger.info(f"Saving audio: {output_path}")
            await self._audio_processor.save_audio(
                audio_data, sample_rate, output_path,
                output_format, self._config.output_bitrate
            )
            
            progress_callback(100)
            
            result = {
                "video_id": video_id,
                "subtitle_path": str(subtitle_path),
                "output_path": str(output_path),
                "engine_used": engine_name.value,
                "total_entries": total_entries,
                "duration": total_duration,
                "sample_rate": sample_rate,
            }
            
            # Add merge info if used
            if merged_entries:
                result["sentence_merge_enabled"] = True
                result["merged_groups"] = len(merged_entries)
            
            return result
            
        finally:
            self._current_task_id = None

    def _combine_segments(self, segments: List[AudioSegment]) -> AudioSegment:
        """Combine multiple audio segments into one."""
        if not segments:
            raise AudioProcessError("No segments to combine")
        
        if len(segments) == 1:
            return segments[0]
        
        # Combine all data
        combined_data = b''.join(s.data for s in segments)
        
        return AudioSegment(
            data=combined_data,
            sample_rate=segments[0].sample_rate,
            channels=segments[0].channels,
            sample_width=segments[0].sample_width,
        )
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel TTS task."""
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
            "subtitle file not found",
            "no subtitle entries",
            "engine not installed",
            "cuda out of memory",
            "out of memory",
        ]
        if any(msg in error_str for msg in non_retryable):
            return False
        
        # Retryable errors
        retryable = [
            "synthesis failed",
            "temporary",
        ]
        return any(msg in error_str for msg in retryable)
    
    # Utility methods
    async def load_engine(self, engine_name: TTSEngine) -> BaseTTSEngine:
        """Load a specific TTS engine."""
        config = TTSConfig(engine=engine_name, use_gpu=self._config.use_gpu)
        engine = create_engine(config)
        await engine.load_model()
        return engine
    
    async def synthesize_text(
        self,
        text: str,
        engine: Optional[BaseTTSEngine] = None,
        speed: float = 1.0,
        speaker: Optional[str] = None,
    ) -> AudioSegment:
        """Synthesize a single text string."""
        if engine is None:
            if self._engine is None:
                self._engine = create_engine(self._config)
                await self._engine.load_model()
            engine = self._engine
        
        return await engine.synthesize(text, speed, speaker)
