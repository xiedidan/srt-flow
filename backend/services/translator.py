"""
Translation Service Module.

Provides subtitle translation using multiple LLM APIs with
batch processing and failover support.
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

class LLMProvider(str, Enum):
    """LLM provider types."""
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"


class Language(str, Enum):
    """Supported languages."""
    AUTO = "auto"
    EN = "en"
    ZH_CN = "zh-CN"
    ZH_TW = "zh-TW"
    JA = "ja"
    KO = "ko"


LANGUAGE_NAMES = {
    Language.EN: "English",
    Language.ZH_CN: "Simplified Chinese",
    Language.ZH_TW: "Traditional Chinese",
    Language.JA: "Japanese",
    Language.KO: "Korean",
}


# ============================================================================
# Exceptions
# ============================================================================

class TranslationError(Exception):
    """Base translation error."""
    pass


class SRTParseError(TranslationError):
    """SRT parsing failed."""
    pass


class LLMError(TranslationError):
    """LLM API error."""
    pass


class AllInstancesFailedError(TranslationError):
    """All LLM instances failed."""
    pass


class ResultMismatchError(TranslationError):
    """Translation result count doesn't match input."""
    pass


class TooManyEmptyLinesError(TranslationError):
    """Too many empty lines in translation result."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SRTEntry:
    """Single SRT subtitle entry."""
    index: int
    start_time: str  # HH:MM:SS,mmm format
    end_time: str
    text: str
    
    def to_srt(self) -> str:
        """Convert to SRT format string."""
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.text}\n"


@dataclass
class LLMInstance:
    """LLM instance configuration."""
    name: str
    provider: LLMProvider
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.3
    enabled: bool = True
    priority: int = 100


@dataclass
class TranslationConfig:
    """Translation service configuration."""
    batch_size: int = 30
    max_tokens_per_batch: int = 5000
    source_language: Language = Language.AUTO
    target_language: Language = Language.ZH_CN
    include_context: bool = True
    max_retries_per_instance: int = 2
    retry_delay: float = 1.0
    llm_instances: List[LLMInstance] = field(default_factory=list)
    # Custom prompts
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    # Task-specific context (user-provided background info)
    task_context: Optional[str] = None
    # Batch overlap: number of lines before/after each batch for context
    context_overlap_lines: int = 0
    # Empty line threshold: max ratio of empty lines before retry (0.0-1.0)
    empty_line_threshold: float = 0.3


# ============================================================================
# SRT Parser
# ============================================================================

class SRTParser:
    """Parses and generates SRT subtitle files."""
    
    # Pattern for SRT timestamp line
    TIMESTAMP_PATTERN = re.compile(
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})'
    )
    
    def __init__(self):
        self._logger = get_logger("translator.srt")
    
    def parse(self, file_path: Path) -> List[SRTEntry]:
        """
        Parse SRT file into entries.
        
        Args:
            file_path: Path to SRT file
            
        Returns:
            List of SRTEntry objects
        """
        if not file_path.exists():
            raise SRTParseError(f"SRT file not found: {file_path}")
        
        content = file_path.read_text(encoding="utf-8")
        return self.parse_content(content)
    
    def parse_content(self, content: str) -> List[SRTEntry]:
        """Parse SRT content string."""
        entries = []
        
        # Split by double newline (entry separator)
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            lines = block.split('\n')
            if len(lines) < 3:
                continue
            
            try:
                # First line: index
                index = int(lines[0].strip())
                
                # Second line: timestamp
                timestamp_match = self.TIMESTAMP_PATTERN.match(lines[1].strip())
                if not timestamp_match:
                    continue
                
                start_time = timestamp_match.group(1)
                end_time = timestamp_match.group(2)
                
                # Remaining lines: text
                text = '\n'.join(lines[2:]).strip()
                
                if text:
                    entries.append(SRTEntry(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        text=text,
                    ))
            except (ValueError, IndexError) as e:
                self._logger.warning(f"Failed to parse block: {e}")
                continue
        
        self._logger.info(f"Parsed {len(entries)} SRT entries")
        return entries
    
    def generate(
        self,
        entries: List[SRTEntry],
        translations: List[str],
        output_path: Path,
    ) -> None:
        """
        Generate translated SRT file.
        
        Handles empty translations by merging with previous entry:
        - Empty translation indicates AI wants to merge with previous line
        - Merged entry uses: previous start_time + current end_time
        
        Args:
            entries: Original SRT entries (for timestamps)
            translations: Translated text list (may contain empty strings for merge)
            output_path: Output file path
        """
        if len(entries) != len(translations):
            raise ResultMismatchError(
                f"Entry count ({len(entries)}) != translation count ({len(translations)})"
            )
        
        # Process entries, merging empty translations with previous
        merged_entries = []
        
        for i, (entry, trans) in enumerate(zip(entries, translations)):
            trans = trans.strip() if trans else ""
            
            if not trans:
                # Empty translation - merge with previous entry
                if merged_entries:
                    prev = merged_entries[-1]
                    # Extend previous entry's end time to current entry's end time
                    merged_entries[-1] = (
                        prev[0],  # start_time (keep previous)
                        entry.end_time,  # end_time (use current)
                        prev[2],  # text (keep previous)
                    )
                    self._logger.debug(
                        f"Merged empty translation at index {i+1} with previous entry"
                    )
                else:
                    # First entry is empty - use placeholder
                    self._logger.warning(
                        f"First translation is empty at index {i+1}, using placeholder"
                    )
                    merged_entries.append((entry.start_time, entry.end_time, "..."))
            else:
                merged_entries.append((entry.start_time, entry.end_time, trans))
        
        # Write merged entries with re-indexed numbers
        with open(output_path, "w", encoding="utf-8") as f:
            for i, (start_time, end_time, text) in enumerate(merged_entries, 1):
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        
        self._logger.info(
            f"Generated SRT with {len(merged_entries)} entries "
            f"(merged {len(entries) - len(merged_entries)} empty translations): {output_path}"
        )


# ============================================================================
# LLM Providers
# ============================================================================

class BaseLLMProvider:
    """Base class for LLM providers."""
    
    # Default system prompt
    DEFAULT_SYSTEM_PROMPT = """You are a professional subtitle translator. Translate subtitles from {source_lang} to {target_lang}.

Requirements:
- Maintain the original tone and style
- Keep translations natural and fluent
- Be concise, suitable for video subtitles
- Output format: numbered lines (e.g., "1. translation")
- Output ONLY the translations, one per line with number prefix
- IMPORTANT: Only translate lines marked with [TRANSLATE], context lines are for reference only"""

    # Default user prompt template
    # All placeholders are replaced with raw data, no extra formatting
    # {task_context} - user-provided background info
    # {video_title} - video title
    # {author} - video channel/author name
    # {description} - video description (truncated to 200 chars)
    # {context_before} - lines before current batch (for continuity)
    # {context_after} - lines after current batch (for continuity)
    # {subtitles} - subtitles to translate
    DEFAULT_USER_PROMPT_TEMPLATE = """{task_context}
{context_before}
{subtitles}
{context_after}"""
    
    def __init__(
        self, 
        instance: LLMInstance,
        system_prompt: Optional[str] = None,
        user_prompt_template: Optional[str] = None,
        task_context: Optional[str] = None,
    ):
        self._instance = instance
        self._logger = get_logger(f"translator.{instance.provider.value}")
        self._system_prompt = system_prompt
        self._user_prompt_template = user_prompt_template
        self._task_context = task_context
    
    async def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> List[str]:
        """Translate a batch of texts."""
        raise NotImplementedError
    
    def _safe_format(self, template: str, **kwargs) -> str:
        """
        Safe string formatting that only replaces known variables.
        Unknown {variables} are left as-is instead of raising KeyError.
        """
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            if var_name in kwargs:
                return str(kwargs[var_name])
            # Leave unknown variables as-is
            return match.group(0)
        
        # Match {variable_name} patterns
        return re.sub(r'\{(\w+)\}', replace_var, template)
    
    def _build_system_prompt(self, source_lang: str, target_lang: str) -> str:
        """Build system prompt with language substitution."""
        source_name = LANGUAGE_NAMES.get(Language(source_lang), source_lang)
        target_name = LANGUAGE_NAMES.get(Language(target_lang), target_lang)
        
        template = self._system_prompt or self.DEFAULT_SYSTEM_PROMPT
        return self._safe_format(
            template,
            source_lang=source_name,
            target_lang=target_name,
        )
    
    def _build_user_prompt(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> str:
        """Build user prompt with context and subtitles."""
        source_name = LANGUAGE_NAMES.get(Language(source_lang), source_lang)
        target_name = LANGUAGE_NAMES.get(Language(target_lang), target_lang)
        
        # Task context - raw data
        task_context_str = self._task_context or ""
        
        # Extract individual video context fields
        video_title = ""
        author = ""
        description = ""
        if context:
            video_title = context.get("title", "")
            author = context.get("channel", "")
            if context.get("description"):
                description = context["description"][:200]
        
        # Context before - raw lines joined
        context_before_str = ""
        if context_before:
            context_before_str = "\n".join(context_before)
        
        # Context after - raw lines joined
        context_after_str = ""
        if context_after:
            context_after_str = "\n".join(context_after)
        
        # Subtitles - simple numbered format
        subtitles_str = "\n".join(f"{i}. {text}" for i, text in enumerate(texts, 1))
        
        template = self._user_prompt_template or self.DEFAULT_USER_PROMPT_TEMPLATE
        return self._safe_format(
            template,
            source_lang=source_name,
            target_lang=target_name,
            task_context=task_context_str,
            video_title=video_title,
            author=author,
            description=description,
            context_before=context_before_str,
            context_after=context_after_str,
            subtitles=subtitles_str,
        )
    
    def _build_prompt(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> str:
        """Build combined prompt (for single-message APIs like Gemini)."""
        system = self._build_system_prompt(source_lang, target_lang)
        user = self._build_user_prompt(texts, source_lang, target_lang, context, context_before, context_after)
        return f"{system}\n\n{user}"
    
    def _build_messages(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Build chat messages for OpenAI-style APIs."""
        system = self._build_system_prompt(source_lang, target_lang)
        user = self._build_user_prompt(texts, source_lang, target_lang, context, context_before, context_after)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    
    def _parse_response(self, response: str, expected_count: int) -> List[str]:
        """
        Parse LLM response to extract translations.
        
        Handles cases where AI returns empty lines with numbers (e.g., "17." with no content),
        which indicates the line should be merged with the previous one.
        Empty translations are marked with a special marker for later processing.
        """
        lines = response.strip().split('\n')
        translations = []
        
        # Pattern to match numbered lines: "1. ", "1: ", "1) ", "1- ", etc.
        number_pattern = re.compile(r'^(\d+)[\.\:\)\-]\s*(.*)')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            match = number_pattern.match(line)
            if match:
                # Line has a number prefix
                content = match.group(2).strip()
                if content:
                    translations.append(content)
                else:
                    # Empty content after number - mark for merge with previous
                    # Use special marker that will be handled in SRT generation
                    translations.append("")
            else:
                # Line without number prefix - might be continuation or noise
                # Only add if it looks like actual content (not just whitespace/punctuation)
                cleaned = line.strip()
                if cleaned and not re.match(r'^[\s\.\,\;\:\-]+$', cleaned):
                    # This might be a continuation of previous line or unnumbered translation
                    # For safety, append it (could be AI formatting variation)
                    translations.append(cleaned)
        
        if len(translations) != expected_count:
            raise ResultMismatchError(
                f"Expected {expected_count} translations, got {len(translations)}"
            )
        
        return translations


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API provider."""
    
    async def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> List[str]:
        """Translate using DeepSeek API."""
        import traceback
        
        try:
            import httpx
            import json
        except ImportError:
            raise LLMError("httpx is required for DeepSeek API")
        
        self._logger.info(f"=== DeepSeek API Request ===")
        self._logger.info(f"Source lang: {source_lang}, Target lang: {target_lang}")
        self._logger.info(f"Texts to translate: {len(texts)} items")
        self._logger.info(f"Context: {context}")
        if context_before:
            self._logger.info(f"Context before: {len(context_before)} lines")
        if context_after:
            self._logger.info(f"Context after: {len(context_after)} lines")
        
        try:
            messages = self._build_messages(texts, source_lang, target_lang, context, context_before, context_after)
            self._logger.info(f"Messages built successfully: {len(messages)} messages")
        except Exception as e:
            self._logger.error(f"Failed to build messages: {type(e).__name__}: {e}")
            self._logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise LLMError(f"Failed to build messages: {e}")
        
        headers = {
            "Authorization": f"Bearer {self._instance.api_key[:8]}***",  # Masked for logging
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._instance.model,
            "messages": messages,
            "temperature": self._instance.temperature,
            "max_tokens": 4096,
        }
        
        url = f"{self._instance.base_url.rstrip('/')}/chat/completions"
        
        # Log request details
        self._logger.info(f"URL: {url}")
        self._logger.info(f"Model: {self._instance.model}")
        self._logger.info(f"Temperature: {self._instance.temperature}")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # Truncate long content for logging
            content_preview = content[:500] + '...' if len(content) > 500 else content
            self._logger.info(f"Message[{i}] role={role}: {content_preview}")
        
        # Actual request with real auth header
        real_headers = {
            "Authorization": f"Bearer {self._instance.api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=real_headers, json=payload)
        
        # Log response details
        self._logger.info(f"=== DeepSeek API Response ===")
        self._logger.info(f"Status code: {response.status_code}")
        
        if response.status_code != 200:
            self._logger.error(f"Response body: {response.text}")
            raise LLMError(f"DeepSeek API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Log full response structure
        self._logger.info(f"Response keys: {list(result.keys())}")
        if "usage" in result:
            self._logger.info(f"Token usage: {result['usage']}")
        
        # Check for API error in response body
        if "error" in result:
            error_msg = result.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            self._logger.error(f"API returned error: {error_msg}")
            raise LLMError(f"DeepSeek API error: {error_msg}")
        
        # Validate response structure
        if "choices" not in result or not result["choices"]:
            self._logger.error(f"Unexpected DeepSeek response: {json.dumps(result, ensure_ascii=False)[:1000]}")
            raise LLMError(f"Invalid DeepSeek response: missing 'choices' field. Response: {str(result)[:500]}")
        
        try:
            message = result["choices"][0]["message"]
            self._logger.info(f"Message keys: {list(message.keys())}")
            
            # DeepSeek reasoner models return reasoning_content instead of content
            content = message.get("content") or message.get("reasoning_content")
            
            if not content:
                self._logger.error(f"No content in DeepSeek response message: {json.dumps(message, ensure_ascii=False)}")
                raise LLMError(f"No content in DeepSeek response. Message keys: {list(message.keys())}")
            
            # Log response content
            content_preview = content[:1000] + '...' if len(content) > 1000 else content
            self._logger.info(f"Response content ({len(content)} chars): {content_preview}")
            
        except (KeyError, IndexError) as e:
            self._logger.error(f"Failed to parse DeepSeek response: {json.dumps(result, ensure_ascii=False)[:1000]}")
            raise LLMError(f"Failed to parse DeepSeek response: {e}. Response: {str(result)[:500]}")
        
        return self._parse_response(content, len(texts))


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""
    
    async def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> List[str]:
        """Translate using OpenAI API."""
        try:
            import httpx
        except ImportError:
            raise LLMError("httpx is required for OpenAI API")
        
        messages = self._build_messages(texts, source_lang, target_lang, context, context_before, context_after)
        
        headers = {
            "Authorization": f"Bearer {self._instance.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._instance.model,
            "messages": messages,
            "temperature": self._instance.temperature,
            "max_tokens": 4096,
        }
        
        url = f"{self._instance.base_url.rstrip('/')}/chat/completions"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise LLMError(f"OpenAI API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Check for API error in response body
        if "error" in result:
            error_msg = result.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            raise LLMError(f"OpenAI API error: {error_msg}")
        
        # Validate response structure
        if "choices" not in result or not result["choices"]:
            self._logger.error(f"Unexpected OpenAI response: {result}")
            raise LLMError(f"Invalid OpenAI response: missing 'choices' field. Response: {str(result)[:500]}")
        
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            self._logger.error(f"Failed to parse OpenAI response: {result}")
            raise LLMError(f"Failed to parse OpenAI response: {e}. Response: {str(result)[:500]}")
        
        return self._parse_response(content, len(texts))


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider."""
    
    async def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> List[str]:
        """Translate using Gemini API."""
        try:
            import httpx
        except ImportError:
            raise LLMError("httpx is required for Gemini API")
        
        prompt = self._build_prompt(texts, source_lang, target_lang, context, context_before, context_after)
        
        # Gemini uses different API structure
        url = f"{self._instance.base_url.rstrip('/')}/models/{self._instance.model}:generateContent"
        url = f"{url}?key={self._instance.api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self._instance.temperature,
                "maxOutputTokens": 4096,
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
        
        if response.status_code != 200:
            raise LLMError(f"Gemini API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        try:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Failed to parse Gemini response: {e}")
        
        return self._parse_response(content, len(texts))


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI-compatible API provider for custom endpoints."""
    
    async def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> List[str]:
        """Translate using OpenAI-compatible API."""
        try:
            import httpx
        except ImportError:
            raise LLMError("httpx is required for OpenAI-compatible API")
        
        messages = self._build_messages(texts, source_lang, target_lang, context, context_before, context_after)
        
        headers = {
            "Authorization": f"Bearer {self._instance.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._instance.model,
            "messages": messages,
            "temperature": self._instance.temperature,
            "max_tokens": 4096,
        }
        
        url = f"{self._instance.base_url.rstrip('/')}/chat/completions"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise LLMError(f"OpenAI-compatible API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Check for API error in response body
        if "error" in result:
            error_msg = result.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            raise LLMError(f"OpenAI-compatible API error: {error_msg}")
        
        # Validate response structure
        if "choices" not in result or not result["choices"]:
            self._logger.error(f"Unexpected OpenAI-compatible response: {result}")
            raise LLMError(f"Invalid OpenAI-compatible response: missing 'choices' field. Response: {str(result)[:500]}")
        
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            self._logger.error(f"Failed to parse OpenAI-compatible response: {result}")
            raise LLMError(f"Failed to parse OpenAI-compatible response: {e}. Response: {str(result)[:500]}")
        
        return self._parse_response(content, len(texts))


def create_provider(
    instance: LLMInstance,
    system_prompt: Optional[str] = None,
    user_prompt_template: Optional[str] = None,
    task_context: Optional[str] = None,
) -> BaseLLMProvider:
    """Factory function to create LLM provider."""
    providers = {
        LLMProvider.DEEPSEEK: DeepSeekProvider,
        LLMProvider.OPENAI: OpenAIProvider,
        LLMProvider.GEMINI: GeminiProvider,
        LLMProvider.OPENAI_COMPATIBLE: OpenAICompatibleProvider,
    }
    
    provider_class = providers.get(instance.provider)
    if not provider_class:
        raise LLMError(f"Unknown provider: {instance.provider}")
    
    return provider_class(instance, system_prompt, user_prompt_template, task_context)


# ============================================================================
# Instance Manager
# ============================================================================

class LLMInstanceManager:
    """Manages LLM instances with priority-based failover."""
    
    def __init__(
        self, 
        instances: List[LLMInstance],
        system_prompt: Optional[str] = None,
        user_prompt_template: Optional[str] = None,
        task_context: Optional[str] = None,
    ):
        # Sort by priority (lower number = higher priority)
        self._instances = sorted(
            [i for i in instances if i.enabled],
            key=lambda x: x.priority
        )
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._logger = get_logger("translator.manager")
        
        # Create providers with custom prompts
        for instance in self._instances:
            self._providers[instance.name] = create_provider(
                instance, system_prompt, user_prompt_template, task_context
            )
        
        self._logger.info(f"Loaded {len(self._instances)} LLM instances")
    
    def get_providers(self) -> List[Tuple[str, BaseLLMProvider]]:
        """Get all providers in priority order."""
        return [(i.name, self._providers[i.name]) for i in self._instances]
    
    def has_providers(self) -> bool:
        """Check if any providers are available."""
        return len(self._instances) > 0


# ============================================================================
# Batch Processor
# ============================================================================

class BatchProcessor:
    """Handles batch translation with failover."""
    
    # Max retries specifically for result mismatch errors (LLM returning wrong count)
    MISMATCH_MAX_RETRIES = 3
    MISMATCH_BASE_DELAY = 2.0  # Base delay in seconds for exponential backoff
    
    # Max retries for empty line threshold exceeded
    EMPTY_LINE_MAX_RETRIES = 2
    EMPTY_LINE_BASE_DELAY = 1.5
    
    def __init__(
        self,
        manager: LLMInstanceManager,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        empty_line_threshold: float = 0.3,
    ):
        self._manager = manager
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._empty_line_threshold = empty_line_threshold
        self._logger = get_logger("translator.batch")
        self._cancelled = False
    
    def _check_empty_lines(self, translations: List[str], batch_size: int) -> None:
        """
        Check if empty line ratio exceeds threshold.
        
        Args:
            translations: List of translated texts
            batch_size: Original batch size
            
        Raises:
            TooManyEmptyLinesError: If empty line ratio exceeds threshold
        """
        if self._empty_line_threshold <= 0:
            return  # Disabled
        
        empty_count = sum(1 for t in translations if not t or not t.strip())
        empty_ratio = empty_count / batch_size if batch_size > 0 else 0
        
        if empty_ratio > self._empty_line_threshold:
            raise TooManyEmptyLinesError(
                f"Empty line ratio {empty_ratio:.1%} exceeds threshold {self._empty_line_threshold:.1%} "
                f"({empty_count}/{batch_size} empty lines)"
            )
    
    async def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[Dict[str, str]] = None,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ) -> Tuple[List[str], str]:
        """
        Translate a batch with failover.
        
        Args:
            texts: Texts to translate
            source_lang: Source language
            target_lang: Target language
            context: Optional video context
            context_before: Optional lines before this batch for context
            context_after: Optional lines after this batch for context
            
        Returns:
            Tuple of (translations, provider_name_used)
        """
        if not self._manager.has_providers():
            raise AllInstancesFailedError("No LLM instances configured")
        
        errors = []
        
        for name, provider in self._manager.get_providers():
            if self._cancelled:
                raise TranslationError("Translation cancelled")
            
            mismatch_attempts = 0
            empty_line_attempts = 0
            
            for attempt in range(self._max_retries + 1):
                if self._cancelled:
                    raise TranslationError("Translation cancelled")
                
                try:
                    self._logger.info(f"Trying {name} (attempt {attempt + 1})")
                    translations = await provider.translate(
                        texts, source_lang, target_lang, context,
                        context_before, context_after
                    )
                    
                    # Check empty line ratio
                    self._check_empty_lines(translations, len(texts))
                    
                    return translations, name
                
                except TooManyEmptyLinesError as e:
                    empty_line_attempts += 1
                    self._logger.warning(
                        f"{name} too many empty lines (attempt {empty_line_attempts}/{self.EMPTY_LINE_MAX_RETRIES}): {e}"
                    )
                    
                    if empty_line_attempts < self.EMPTY_LINE_MAX_RETRIES:
                        delay = self.EMPTY_LINE_BASE_DELAY * (2 ** (empty_line_attempts - 1))
                        self._logger.info(f"Retrying {name} after {delay:.1f}s backoff due to empty lines...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        errors.append(f"{name}: {e} (after {empty_line_attempts} empty line retries)")
                        break
                    
                except ResultMismatchError as e:
                    mismatch_attempts += 1
                    self._logger.warning(
                        f"{name} result mismatch (attempt {mismatch_attempts}/{self.MISMATCH_MAX_RETRIES}): {e}"
                    )
                    
                    # Retry with exponential backoff for mismatch errors
                    if mismatch_attempts < self.MISMATCH_MAX_RETRIES:
                        delay = self.MISMATCH_BASE_DELAY * (2 ** (mismatch_attempts - 1))
                        self._logger.info(f"Retrying {name} after {delay:.1f}s backoff...")
                        await asyncio.sleep(delay)
                        # Don't increment attempt counter, this is a mismatch-specific retry
                        continue
                    else:
                        # Exhausted mismatch retries, record error and try next provider
                        errors.append(f"{name}: {e} (after {mismatch_attempts} mismatch retries)")
                        break
                    
                except LLMError as e:
                    self._logger.warning(f"{name} error: {e}")
                    errors.append(f"{name}: {e}")
                    
                    if attempt < self._max_retries:
                        delay = self._retry_delay * (2 ** attempt)
                        self._logger.info(f"Retrying {name} after {delay:.1f}s backoff...")
                        await asyncio.sleep(delay)
                    else:
                        break
                    
                except Exception as e:
                    import traceback
                    self._logger.error(f"{name} unexpected error: {type(e).__name__}: {e}")
                    self._logger.error(f"Full traceback:\n{traceback.format_exc()}")
                    
                    # Retry with exponential backoff for unexpected errors (e.g., ReadTimeout)
                    if attempt < self._max_retries:
                        delay = self._retry_delay * (2 ** attempt)
                        self._logger.info(f"Retrying {name} after {delay:.1f}s backoff due to unexpected error...")
                        await asyncio.sleep(delay)
                    else:
                        errors.append(f"{name}: {type(e).__name__}: {e}")
                        break
        
        raise AllInstancesFailedError(f"All instances failed: {'; '.join(errors)}")
    
    def cancel(self) -> None:
        """Cancel ongoing translation."""
        self._cancelled = True


# ============================================================================
# Translation Service
# ============================================================================

class TranslationService(BaseService):
    """
    Subtitle translation service.
    
    Implements BaseService interface for worker integration.
    Supports multiple LLM providers with failover.
    """
    
    def __init__(self, config: Optional[TranslationConfig] = None):
        """
        Initialize translation service.
        
        Args:
            config: Translation configuration
        """
        self._config = config or TranslationConfig()
        self._logger = get_logger("translator")
        self._srt_parser = SRTParser()
        self._instance_manager: Optional[LLMInstanceManager] = None
        self._batch_processor: Optional[BatchProcessor] = None
        self._current_task_id: Optional[str] = None
    
    def _init_manager(self) -> None:
        """Initialize LLM instance manager."""
        if self._instance_manager is None:
            self._instance_manager = LLMInstanceManager(
                self._config.llm_instances,
                system_prompt=self._config.system_prompt,
                user_prompt_template=self._config.user_prompt_template,
                task_context=self._config.task_context,
            )
            self._batch_processor = BatchProcessor(
                self._instance_manager,
                max_retries=self._config.max_retries_per_instance,
                retry_delay=self._config.retry_delay,
                empty_line_threshold=self._config.empty_line_threshold,
            )
    
    async def execute(
        self,
        task: Task,
        progress_callback: ProgressCallback,
        payload_callback=None,
    ) -> Dict[str, Any]:
        """
        Execute translation task.
        
        Args:
            task: Translation task
            progress_callback: Progress callback
            payload_callback: Optional callback to update task payload (unused)
            
        Returns:
            Translation result
        """
        self._current_task_id = task.id
        payload = task.payload or {}
        
        video_id = payload.get("video_id")
        subtitle_path = payload.get("subtitle_path")
        
        if not subtitle_path:
            raise TranslationError("subtitle_path is required")
        
        subtitle_path = Path(subtitle_path)
        if not subtitle_path.exists():
            raise TranslationError(f"Subtitle file not found: {subtitle_path}")
        
        # Get config from payload or use defaults
        source_lang = payload.get("source_language", self._config.source_language.value)
        target_lang = payload.get("target_language", self._config.target_language.value)
        batch_size = payload.get("batch_size", self._config.batch_size)
        resume_from = payload.get("resume_from_batch", 0)
        
        # Video context for better translation
        context = None
        if self._config.include_context:
            context = {
                "title": payload.get("video_title"),
                "channel": payload.get("channel_name"),
                "description": payload.get("video_description"),
            }
        
        output_path = subtitle_path.parent / "subtitle_translated.srt"
        
        try:
            self._init_manager()
            
            # Parse SRT
            progress_callback(0)
            self._logger.info(f"Parsing SRT: {subtitle_path}")
            entries = self._srt_parser.parse(subtitle_path)
            
            if not entries:
                raise TranslationError("No subtitle entries found")
            
            # Split into batches
            batches = self._split_batches(entries, batch_size)
            total_batches = len(batches)
            
            # Get overlap lines config
            overlap_lines = payload.get("context_overlap_lines", self._config.context_overlap_lines)
            
            self._logger.info(f"Split into {total_batches} batches of ~{batch_size} entries, overlap={overlap_lines}")
            
            # Translate batches
            all_translations = []
            providers_used = set()
            
            # Build flat list of all texts for overlap context
            all_texts = [e.text for e in entries]
            
            # Track batch boundaries for overlap
            batch_start_indices = []
            current_idx = 0
            for batch in batches:
                batch_start_indices.append(current_idx)
                current_idx += len(batch)
            
            for i, batch in enumerate(batches):
                if i < resume_from:
                    # Skip already processed batches (for resume)
                    continue
                
                batch_texts = [e.text for e in batch]
                batch_start = batch_start_indices[i]
                batch_end = batch_start + len(batch)
                
                # Get context lines before and after this batch
                context_before = None
                context_after = None
                
                if overlap_lines > 0:
                    # Get N lines before this batch
                    before_start = max(0, batch_start - overlap_lines)
                    if before_start < batch_start:
                        context_before = all_texts[before_start:batch_start]
                    
                    # Get N lines after this batch
                    after_end = min(len(all_texts), batch_end + overlap_lines)
                    if after_end > batch_end:
                        context_after = all_texts[batch_end:after_end]
                
                translations, provider_name = await self._batch_processor.translate_batch(
                    batch_texts, source_lang, target_lang, context,
                    context_before, context_after
                )
                
                all_translations.extend(translations)
                providers_used.add(provider_name)
                
                # Update progress
                progress = int(((i + 1) / total_batches) * 100)
                progress_callback(progress)
                
                self._logger.info(f"Batch {i + 1}/{total_batches} done via {provider_name}")
            
            # Generate output SRT
            self._srt_parser.generate(entries, all_translations, output_path)
            
            progress_callback(100)
            
            # Build prompt info for result (for task detail viewing)
            prompt_info = {
                "system_prompt": self._config.system_prompt or BaseLLMProvider.DEFAULT_SYSTEM_PROMPT,
                "user_prompt_template": self._config.user_prompt_template or BaseLLMProvider.DEFAULT_USER_PROMPT_TEMPLATE,
                "task_context": self._config.task_context,
                "context_overlap_lines": overlap_lines,
            }
            
            return {
                "video_id": video_id,
                "source_path": str(subtitle_path),
                "output_path": str(output_path),
                "source_language": source_lang,
                "target_language": target_lang,
                "total_entries": len(entries),
                "batches_processed": total_batches,
                "providers_used": list(providers_used),
                "prompt_info": prompt_info,
                "context_overlap_lines": overlap_lines,
            }
            
        finally:
            self._current_task_id = None

    def _split_batches(
        self,
        entries: List[SRTEntry],
        batch_size: int,
    ) -> List[List[SRTEntry]]:
        """Split entries into batches."""
        batches = []
        current_batch = []
        current_tokens = 0
        
        for entry in entries:
            # Rough token estimate (chars / 4)
            entry_tokens = len(entry.text) // 4 + 1
            
            # Check if adding this entry exceeds limits
            if (len(current_batch) >= batch_size or
                current_tokens + entry_tokens > self._config.max_tokens_per_batch):
                if current_batch:
                    batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            
            current_batch.append(entry)
            current_tokens += entry_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel translation task."""
        if self._current_task_id != task_id:
            return False
        
        if self._batch_processor:
            self._batch_processor.cancel()
        
        return True
    
    def can_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        error_str = str(error).lower()
        
        # Non-retryable errors
        non_retryable = [
            "file not found",
            "subtitle file not found",
            "no subtitle entries",
            "all instances failed",
            "no llm instances configured",
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
    def parse_srt(self, file_path: Path) -> List[SRTEntry]:
        """Parse SRT file."""
        return self._srt_parser.parse(file_path)
    
    def generate_srt(
        self,
        entries: List[SRTEntry],
        translations: List[str],
        output_path: Path,
    ) -> None:
        """Generate translated SRT file."""
        self._srt_parser.generate(entries, translations, output_path)
