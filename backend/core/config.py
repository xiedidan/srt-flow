"""
Configuration Manager Module.

Provides unified configuration management for SRT Flow:
- System configuration from .env files
- User configuration from SQLite database
- Sensitive data encryption (API keys)
- Configuration validation and caching
"""
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar
from datetime import datetime
from enum import Enum
from functools import lru_cache

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

from backend.core.encryption import EncryptionManager, get_encryption_manager
from backend.core.exceptions import (
    ConfigNotFoundError,
    ConfigValidationError,
    ConfigDecryptionError,
)


# Load .env file
load_dotenv()


# ============================================================================
# System Settings (from .env)
# ============================================================================

class SystemSettings(BaseSettings):
    """
    System-level configuration loaded from environment variables.
    
    These settings are typically set at deployment time and rarely change.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8010, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Database
    database_path: str = Field(default="data/srtflow.db", alias="DATABASE_PATH")
    
    # File Storage
    data_dir: str = Field(default="data", alias="DATA_DIR")
    downloads_dir: str = Field(default="data/downloads", alias="DOWNLOADS_DIR")
    
    # Security
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    encryption_key: Optional[str] = Field(default=None, alias="ENCRYPTION_KEY")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: str = Field(default="data/logs", alias="LOG_DIR")
    
    # External Tools
    ffmpeg_path: str = Field(default="ffmpeg", alias="FFMPEG_PATH")
    ytdlp_path: str = Field(default="yt-dlp", alias="YTDLP_PATH")
    
    # GPU
    cuda_visible_devices: Optional[str] = Field(default=None, alias="CUDA_VISIBLE_DEVICES")


@lru_cache()
def get_system_settings() -> SystemSettings:
    """Get cached system settings instance."""
    return SystemSettings()


# ============================================================================
# Configuration Models (for SQLite storage)
# ============================================================================

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class VideoQuality(str, Enum):
    BEST = "best"
    HIGH = "1080p"
    MEDIUM = "720p"
    LOW = "480p"


class ASREngine(str, Enum):
    FASTER_WHISPER_XXL = "faster_whisper_xxl"
    GEMINI = "gemini"


class WhisperModelSize(str, Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"


class ComputeDevice(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"


class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"


class TTSEngine(str, Enum):
    COQUI = "coqui"
    CHATTTS = "chattts"
    SPARKTTS = "sparktts"
    INDEXTTS = "indextts"
    COZYVOICE = "cozyvoice"
    VITS = "vits"
    # Online TTS services
    AZURE_TTS = "azure_tts"
    EDGE_TTS = "edge_tts"
    VOLC_TTS = "volc_tts"


class AudioFormat(str, Enum):
    WAV = "wav"
    M4A = "m4a"
    MP3 = "mp3"


class SubtitlePosition(str, Enum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


# ============================================================================
# Configuration Schemas
# ============================================================================

class GlobalConfig(BaseModel):
    """Global configuration shared across all services."""
    default_source_language: str = "en"
    default_target_language: str = "zh-CN"
    log_level: LogLevel = LogLevel.INFO
    max_concurrent_tasks: int = Field(default=1, ge=1, le=10)
    proxy_url: Optional[str] = None  # Global proxy for downloads, API calls, etc.


class CookiesBrowser(str, Enum):
    """Browser for cookies extraction."""
    NONE = "none"
    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"
    SAFARI = "safari"
    OPERA = "opera"
    BRAVE = "brave"


class DownloadConfig(BaseModel):
    """Download service configuration."""
    preferred_quality: VideoQuality = VideoQuality.BEST
    download_subtitles: bool = True
    cookies_browser: CookiesBrowser = CookiesBrowser.NONE
    nodejs_path: Optional[str] = None  # Path to Node.js executable for YouTube n-parameter solving
    # proxy_url removed - use global proxy from GlobalConfig instead
    allowed_time_start: Optional[str] = None  # HH:MM format
    allowed_time_end: Optional[str] = None
    
    @field_validator("allowed_time_start", "allowed_time_end")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError("Time must be in HH:MM format")


class ASRConfig(BaseModel):
    """Speech recognition configuration."""
    engine: ASREngine = ASREngine.FASTER_WHISPER_XXL
    whisper_model_size: WhisperModelSize = WhisperModelSize.LARGE_V3
    whisper_extra_args: str = ""  # Extra command line arguments for Whisper
    device: ComputeDevice = ComputeDevice.AUTO
    
    # Gemini API settings (new: use AI Provider)
    gemini_provider_id: Optional[str] = None  # Reference to ai_providers.id
    gemini_model: str = "gemini-1.5-flash"  # Model to use for Gemini ASR
    
    # Legacy fields (for backward compatibility)
    gemini_base_url: Optional[str] = None  # Custom API URL for third-party Gemini services
    gemini_api_key: Optional[str] = Field(default=None, exclude=True)


class TranslateConfig(BaseModel):
    """Translation service configuration."""
    # AI Provider selection
    ai_provider_id: Optional[str] = None  # Reference to ai_providers.id
    model_name: str = "deepseek-chat"
    
    # Translation parameters
    batch_size: int = Field(default=30, ge=1, le=100)
    context_overlap_lines: int = Field(default=3, ge=0, le=10)  # Lines before/after each batch for context
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    empty_line_threshold: float = Field(default=0.3, ge=0.0, le=1.0)  # Max ratio of empty lines before retry
    
    # Custom prompts for translation
    system_prompt: Optional[str] = None  # Custom system prompt, None uses default
    user_prompt_template: Optional[str] = None  # Custom user prompt template, None uses default


class TTSConfig(BaseModel):
    """Text-to-speech configuration."""
    engine: TTSEngine = TTSEngine.INDEXTTS
    output_format: AudioFormat = AudioFormat.M4A
    speed_factor: float = Field(default=1.0, ge=0.5, le=2.0)
    use_gpu: bool = True
    
    # Common settings
    reference_audio: Optional[str] = None  # Path to reference audio for voice cloning
    
    # Sentence merge settings (AI-powered)
    enable_sentence_merge: bool = False  # Enable AI sentence merging before TTS
    sentence_merge_provider_id: Optional[str] = None  # Reference to ai_providers.id
    sentence_merge_model: str = "deepseek-chat"  # Model for sentence merging
    sentence_merge_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    sentence_merge_system_prompt: Optional[str] = None  # Custom system prompt
    sentence_merge_user_prompt: Optional[str] = None  # Custom user prompt template
    
    # ChatTTS settings
    chattts_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    chattts_top_p: float = Field(default=0.7, ge=0.0, le=1.0)
    chattts_top_k: int = Field(default=20, ge=1, le=100)
    
    # IndexTTS settings (API mode)
    indextts_mode: str = "local"  # "local" or "api"
    indextts_api_url: Optional[str] = None  # API endpoint for remote IndexTTS
    
    # SparkTTS settings (API mode)
    sparktts_mode: str = "local"  # "local" or "api"
    sparktts_api_url: Optional[str] = None  # API endpoint for remote SparkTTS
    
    # CozyVoice settings
    cozyvoice_mode: str = "local"  # "local" or "api"
    cozyvoice_api_url: Optional[str] = None  # API endpoint for remote CozyVoice
    cozyvoice_speaker: str = "中文女"  # Default speaker for SFT mode
    
    # Coqui TTS settings
    coqui_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    
    # VITS settings
    vits_model_path: Optional[str] = None
    
    # Azure TTS settings (online service)
    azure_tts_voice: str = "zh-CN-XiaoxiaoMultilingualNeural"
    azure_tts_style: str = "general"
    azure_tts_rate: str = "0"  # Percentage adjustment, e.g., "0", "+10", "-10"
    azure_tts_pitch: str = "0"  # Percentage adjustment
    
    # Edge TTS settings (online service)
    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_tts_rate: str = "+0%"  # e.g., "+0%", "+10%", "-10%"
    edge_tts_pitch: str = "+0Hz"  # e.g., "+0Hz", "+10Hz"
    
    # Volc TTS settings (online service)
    volc_tts_voice: str = "zh_female_qingxin"


class VideoEncoder(str, Enum):
    """Video encoder options."""
    H264_SOFTWARE = "libx264"
    H264_NVENC = "h264_nvenc"
    H265_SOFTWARE = "libx265"
    H265_NVENC = "hevc_nvenc"


class SynthesisConfig(BaseModel):
    """Video synthesis configuration."""
    # Encoding settings
    video_encoder: VideoEncoder = VideoEncoder.H264_SOFTWARE
    video_crf: int = Field(default=23, ge=0, le=51)
    video_preset: str = "medium"  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
    
    # Audio settings
    mute_original: bool = False
    original_volume: float = Field(default=0.3, ge=0.0, le=1.0)
    tts_volume: float = Field(default=1.0, ge=0.0, le=2.0)
    
    # Original subtitle style (displayed at bottom, smaller, white semi-transparent)
    original_subtitle_font: str = "Microsoft YaHei"
    original_subtitle_font_size: int = Field(default=18, ge=12, le=200)
    original_subtitle_bold: bool = False
    original_subtitle_color: str = "#FFFFFF"
    original_subtitle_alpha: float = Field(default=0.85, ge=0.0, le=1.0)
    original_subtitle_outline_color: str = "#000000"
    original_subtitle_outline_width: int = Field(default=1, ge=0, le=10)
    original_subtitle_shadow_enabled: bool = False
    original_subtitle_shadow_offset: int = Field(default=1, ge=0, le=10)
    original_subtitle_position: SubtitlePosition = SubtitlePosition.BOTTOM
    original_subtitle_margin_v: int = Field(default=30, ge=0, le=500)
    original_subtitle_background_enabled: bool = False
    original_subtitle_background_color: str = "#000000"
    original_subtitle_background_alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    original_subtitle_background_padding_h: int = Field(default=10, ge=0, le=100)
    original_subtitle_background_padding_v: int = Field(default=5, ge=0, le=100)
    
    # Translated subtitle style (displayed above original, larger, yellow semi-transparent)
    translated_subtitle_font: str = "Microsoft YaHei"
    translated_subtitle_font_size: int = Field(default=24, ge=12, le=200)
    translated_subtitle_bold: bool = False
    translated_subtitle_color: str = "#FFFACD"
    translated_subtitle_alpha: float = Field(default=0.85, ge=0.0, le=1.0)
    translated_subtitle_outline_color: str = "#000000"
    translated_subtitle_outline_width: int = Field(default=2, ge=0, le=10)
    translated_subtitle_shadow_enabled: bool = False
    translated_subtitle_shadow_offset: int = Field(default=1, ge=0, le=10)
    translated_subtitle_position: SubtitlePosition = SubtitlePosition.BOTTOM
    translated_subtitle_margin_v: int = Field(default=60, ge=0, le=500)
    translated_subtitle_background_enabled: bool = False
    translated_subtitle_background_color: str = "#000000"
    translated_subtitle_background_alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    translated_subtitle_background_padding_h: int = Field(default=10, ge=0, le=100)
    translated_subtitle_background_padding_v: int = Field(default=5, ge=0, le=100)


class AssetConfig(BaseModel):
    """Asset generation configuration."""
    # Summary generation AI config
    summary_ai_provider_id: Optional[str] = None
    summary_model_name: str = "deepseek-chat"
    summary_temperature: float = Field(default=0.65, ge=0.0, le=2.0)
    summary_system_prompt: Optional[str] = None
    summary_user_prompt_template: Optional[str] = None
    
    # Title generation AI config
    title_count: int = Field(default=3, ge=1, le=10)
    title_ai_provider_id: Optional[str] = None
    title_model_name: str = "deepseek-chat"
    title_temperature: float = Field(default=0.85, ge=0.0, le=2.0)
    title_system_prompt: Optional[str] = None
    title_user_prompt_template: Optional[str] = None
    
    # Thumbnail generation config (used when task specifies AI mode)
    # Text model for generating image prompt
    thumbnail_ai_provider_id: Optional[str] = None
    thumbnail_model_name: str = "deepseek-chat"
    thumbnail_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    thumbnail_system_prompt: Optional[str] = None
    thumbnail_user_prompt_template: Optional[str] = None
    
    # Image generation API config (for calling text-to-image API)
    thumbnail_image_provider: str = "dall-e"  # dall-e, midjourney, stable-diffusion
    thumbnail_image_api_key: Optional[str] = None  # Encrypted
    thumbnail_image_base_url: Optional[str] = None
    thumbnail_image_model: str = "dall-e-3"


# Type variable for config models
ConfigT = TypeVar("ConfigT", bound=BaseModel)

# Mapping of category names to config models
CONFIG_MODELS: Dict[str, Type[BaseModel]] = {
    "global": GlobalConfig,
    "download": DownloadConfig,
    "asr": ASRConfig,
    "translate": TranslateConfig,
    "tts": TTSConfig,
    "synthesis": SynthesisConfig,
    "asset": AssetConfig,
}

# Fields that should be encrypted
SENSITIVE_FIELDS: Dict[str, List[str]] = {
    "asr": ["gemini_api_key"],
    "asset": ["thumbnail_image_api_key"],
}


# ============================================================================
# Configuration Manager
# ============================================================================

class ConfigManager:
    """
    Unified configuration manager for SRT Flow.
    
    Manages both system settings (.env) and user configurations (SQLite).
    Provides encryption for sensitive data and caching for performance.
    """
    
    def __init__(self, db_session=None):
        """
        Initialize configuration manager.
        
        Args:
            db_session: SQLAlchemy async session (optional, for SQLite configs)
        """
        self._db_session = db_session
        self._system_settings = get_system_settings()
        self._encryption = get_encryption_manager(self._system_settings.data_dir)
        self._cache: Dict[str, BaseModel] = {}
        self._secrets_cache: Dict[str, Dict[str, str]] = {}
    
    @property
    def system(self) -> SystemSettings:
        """Get system settings."""
        return self._system_settings
    
    def set_db_session(self, session) -> None:
        """Set database session for SQLite operations."""
        self._db_session = session
    
    def clear_cache(self, category: Optional[str] = None) -> None:
        """
        Clear configuration cache.
        
        Args:
            category: Specific category to clear, or None for all
        """
        if category:
            self._cache.pop(category, None)
            self._secrets_cache.pop(category, None)
        else:
            self._cache.clear()
            self._secrets_cache.clear()
    
    def get_default_config(self, category: str) -> BaseModel:
        """
        Get default configuration for a category.
        
        Args:
            category: Configuration category name
            
        Returns:
            Default configuration model instance
        """
        if category not in CONFIG_MODELS:
            raise ConfigValidationError(f"Unknown config category: {category}")
        return CONFIG_MODELS[category]()
    
    async def get_config(self, category: str, use_cache: bool = True) -> BaseModel:
        """
        Get configuration for a category.
        
        Args:
            category: Configuration category name
            use_cache: Whether to use cached value
            
        Returns:
            Configuration model instance
        """
        if category not in CONFIG_MODELS:
            raise ConfigValidationError(f"Unknown config category: {category}")
        
        # Check cache
        if use_cache and category in self._cache:
            return self._cache[category]
        
        # Load from database
        config_data = await self._load_from_db(category)
        
        # Create model with defaults merged
        model_class = CONFIG_MODELS[category]
        config = model_class(**config_data) if config_data else model_class()
        
        # Cache and return
        self._cache[category] = config
        return config
    
    async def update_config(
        self, 
        category: str, 
        updates: Dict[str, Any],
        validate: bool = True
    ) -> BaseModel:
        """
        Update configuration for a category.
        
        Args:
            category: Configuration category name
            updates: Dictionary of fields to update
            validate: Whether to validate before saving
            
        Returns:
            Updated configuration model
        """
        if category not in CONFIG_MODELS:
            raise ConfigValidationError(f"Unknown config category: {category}")
        
        # Get current config
        current = await self.get_config(category, use_cache=False)
        current_data = current.model_dump()
        
        # Merge updates
        current_data.update(updates)
        
        # Validate
        model_class = CONFIG_MODELS[category]
        if validate:
            try:
                new_config = model_class(**current_data)
            except Exception as e:
                raise ConfigValidationError(f"Validation failed: {e}")
        else:
            new_config = model_class.model_construct(**current_data)
        
        # Save to database
        await self._save_to_db(category, new_config.model_dump())
        
        # Update cache
        self._cache[category] = new_config
        return new_config
    
    async def reset_config(self, category: str) -> BaseModel:
        """
        Reset configuration to defaults.
        
        Args:
            category: Configuration category name
            
        Returns:
            Default configuration model
        """
        if category not in CONFIG_MODELS:
            raise ConfigValidationError(f"Unknown config category: {category}")
        
        default_config = CONFIG_MODELS[category]()
        await self._save_to_db(category, default_config.model_dump())
        self._cache[category] = default_config
        return default_config
    
    # ========================================================================
    # Sensitive Data Management
    # ========================================================================
    
    async def get_api_key(self, category: str, key_name: str) -> Optional[str]:
        """
        Get decrypted API key (internal use only).
        
        Args:
            category: Configuration category
            key_name: Name of the API key field
            
        Returns:
            Decrypted API key or None
        """
        # Check cache
        if category in self._secrets_cache:
            if key_name in self._secrets_cache[category]:
                return self._secrets_cache[category][key_name]
        
        # Load from database
        encrypted = await self._load_secret_from_db(category, key_name)
        if not encrypted:
            return None
        
        # Decrypt
        try:
            decrypted = self._encryption.decrypt(encrypted)
        except ConfigDecryptionError:
            return None
        
        # Cache
        if category not in self._secrets_cache:
            self._secrets_cache[category] = {}
        self._secrets_cache[category][key_name] = decrypted
        
        return decrypted
    
    async def set_api_key(self, category: str, key_name: str, value: str) -> None:
        """
        Set and encrypt API key.
        
        Args:
            category: Configuration category
            key_name: Name of the API key field
            value: Plain text API key
        """
        # Validate field is a known sensitive field
        if category not in SENSITIVE_FIELDS or key_name not in SENSITIVE_FIELDS[category]:
            raise ConfigValidationError(f"Unknown sensitive field: {category}.{key_name}")
        
        # Encrypt and save
        encrypted = self._encryption.encrypt(value)
        await self._save_secret_to_db(category, key_name, encrypted)
        
        # Update cache
        if category not in self._secrets_cache:
            self._secrets_cache[category] = {}
        self._secrets_cache[category][key_name] = value
    
    async def get_masked_api_key(self, category: str, key_name: str) -> str:
        """
        Get masked API key for display.
        
        Args:
            category: Configuration category
            key_name: Name of the API key field
            
        Returns:
            Masked API key (e.g., "sk-a***") or empty string
        """
        value = await self.get_api_key(category, key_name)
        return EncryptionManager.mask_sensitive(value) if value else ""
    
    async def has_api_key(self, category: str, key_name: str) -> bool:
        """Check if an API key is configured."""
        value = await self.get_api_key(category, key_name)
        return bool(value)
    
    # ========================================================================
    # Export/Import
    # ========================================================================
    
    async def export_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Export all configurations.
        
        Args:
            include_secrets: Whether to include masked secrets
            
        Returns:
            Dictionary of all configurations
        """
        result = {}
        for category in CONFIG_MODELS:
            config = await self.get_config(category)
            # Explicitly include None values to ensure all fields are exported
            result[category] = config.model_dump(exclude_none=False)
            
            # Add masked secrets if requested
            if include_secrets and category in SENSITIVE_FIELDS:
                for key_name in SENSITIVE_FIELDS[category]:
                    masked = await self.get_masked_api_key(category, key_name)
                    result[category][f"{key_name}_masked"] = masked
        
        return result
    
    async def import_config(self, data: Dict[str, Any]) -> None:
        """
        Import configurations (excludes secrets).
        
        Args:
            data: Dictionary of configurations to import
        """
        for category, config_data in data.items():
            if category in CONFIG_MODELS:
                # Filter out any secret fields
                if category in SENSITIVE_FIELDS:
                    for key_name in SENSITIVE_FIELDS[category]:
                        config_data.pop(key_name, None)
                        config_data.pop(f"{key_name}_masked", None)
                
                await self.update_config(category, config_data)
    
    # ========================================================================
    # Database Operations (to be implemented with actual DB)
    # ========================================================================
    
    async def _load_from_db(self, category: str) -> Dict[str, Any]:
        """Load configuration from database."""
        if self._db_session is None:
            return {}
        
        from backend.core.repositories import ConfigRepository
        repo = ConfigRepository(self._db_session)
        config_dict = await repo.get_category_dict(category)
        
        # Get model class to check field types
        model_class = CONFIG_MODELS.get(category)
        model_fields = model_class.model_fields if model_class else {}
        
        # Convert string values back to proper types
        result = {}
        for key, value_str in config_dict.items():
            try:
                # Try to parse as JSON for complex types
                import json
                parsed_value = json.loads(value_str)
                
                # Check if field expects string but got int/float (e.g., "0" parsed as 0)
                if key in model_fields:
                    field_annotation = model_fields[key].annotation
                    # Handle Optional[str] and str types
                    if field_annotation == str or (
                        hasattr(field_annotation, '__origin__') and 
                        str in getattr(field_annotation, '__args__', ())
                    ):
                        if isinstance(parsed_value, (int, float)) and not isinstance(parsed_value, bool):
                            parsed_value = str(parsed_value)
                
                result[key] = parsed_value
            except (json.JSONDecodeError, TypeError):
                # Keep as string if not valid JSON
                result[key] = value_str
        
        return result
    
    async def _save_to_db(self, category: str, data: Dict[str, Any]) -> None:
        """Save configuration to database."""
        if self._db_session is None:
            return
        
        from backend.core.repositories import ConfigRepository
        import json
        from enum import Enum
        
        repo = ConfigRepository(self._db_session)
        
        # Save each key-value pair
        for key, value in data.items():
            # Convert value to string (JSON for complex types)
            if isinstance(value, Enum):
                # For enums, save the value (not the string representation)
                value_str = json.dumps(value.value)
            elif isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            elif isinstance(value, bool):
                value_str = json.dumps(value)
            elif value is None:
                value_str = json.dumps(None)
            else:
                value_str = str(value)
            
            await repo.set_value(
                category=category,
                key=key,
                value=value_str,
                is_encrypted=False,
            )
    
    async def _load_secret_from_db(self, category: str, key_name: str) -> Optional[str]:
        """Load encrypted secret from database."""
        if self._db_session is None:
            return None
        
        from backend.core.repositories import ConfigRepository
        repo = ConfigRepository(self._db_session)
        config = await repo.get_by_key(category, key_name)
        
        if config and config.is_encrypted:
            return config.value
        return None
    
    async def _save_secret_to_db(
        self, 
        category: str, 
        key_name: str, 
        encrypted_value: str
    ) -> None:
        """Save encrypted secret to database."""
        if self._db_session is None:
            return
        
        from backend.core.repositories import ConfigRepository
        repo = ConfigRepository(self._db_session)
        await repo.set_value(
            category=category,
            key=key_name,
            value=encrypted_value,
            is_encrypted=True,
        )


# ============================================================================
# Global Instance
# ============================================================================

_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


async def init_config_manager(db_session=None) -> ConfigManager:
    """Initialize configuration manager with database session."""
    global _config_manager
    _config_manager = ConfigManager(db_session)
    return _config_manager
