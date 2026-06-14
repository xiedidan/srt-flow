"""
Services module for SRT Flow business logic.

This package contains business service implementations:
- download: Video download service (yt-dlp, BiliDown)
- media: Media management service
- asr: Speech recognition service (Whisper, Gemini, OpenAI)
- translator: Translation service (DeepSeek, Gemini, OpenAI)
- tts: Text-to-speech service (ChatTTS, Coqui, VITS)
- synthesizer: Video synthesis service (FFmpeg)
- asset_gen: Asset generation service (LLM, FFmpeg)
- editor: Video editing service (FFmpeg)
"""
from backend.services.download import (
    # Service
    DownloadService,
    DownloadConfig,
    # Types
    DownloadChannel,
    VideoQuality,
    # Utilities
    URLParser,
    ProgressParser,
    DirectoryManager,
    MetadataExtractor,
    # Exceptions
    DownloadError,
    UnsupportedURLError,
    ChannelIncompatibleError,
    DuplicateVideoError,
    DownloadFailedError,
)

from backend.services.media import (
    # Service
    MediaService,
    MediaConfig,
    # Types
    VideoFilter,
    FileScanner,
    # Constants
    FILE_PATTERNS,
    AUTO_TAG_RULES,
    FILE_AUTO_TAGS,
    TAG_COLORS,
)

from backend.services.asr import (
    # Service
    ASRService,
    ASRConfig,
    # Types
    ASRChannel,
    WhisperModel,
    ComputeType,
    # Utilities
    AudioExtractor,
    WhisperTranscriber,
    SRTGenerator,
    SRTSegment,
    OpenAITranscriber,
    GeminiTranscriber,
    # Exceptions
    ASRError,
    AudioExtractionError,
    ModelLoadError,
    TranscriptionError,
    APIError,
)

from backend.services.translator import (
    # Service
    TranslationService,
    TranslationConfig,
    # Types
    LLMProvider,
    Language,
    SRTEntry,
    LLMInstance,
    # Utilities
    SRTParser,
    LLMInstanceManager,
    BatchProcessor,
    # Providers
    DeepSeekProvider,
    OpenAIProvider as TranslatorOpenAIProvider,
    GeminiProvider as TranslatorGeminiProvider,
    # Exceptions
    TranslationError,
    SRTParseError,
    LLMError,
    AllInstancesFailedError,
    ResultMismatchError,
)

from backend.services.tts import (
    # Service
    TTSService,
    TTSConfig,
    # Types
    TTSEngine,
    OutputFormat,
    SubtitleEntry,
    AudioSegment,
    # Engines
    BaseTTSEngine,
    ChatTTSEngine,
    CoquiTTSEngine,
    VITSEngine,
    # Utilities
    SpeedCalculator,
    TextSplitter,
    AudioProcessor,
    # Exceptions
    TTSError,
    EngineLoadError,
    SynthesisError,
    AudioProcessError,
)

from backend.services.synthesizer import (
    # Service
    SynthesizerService,
    SynthesizerConfig,
    # Types
    SubtitleMode,
    VideoCodec,
    HardwareAccel,
    SubtitlePosition,
    SubtitleStyle,
    StylePreset,
    # Utilities
    FFmpegCommandBuilder,
    FFmpegProgressParser,
    # Constants
    DEFAULT_PRESETS,
    # Exceptions
    SynthesizerError,
    FFmpegError,
    InputFileError,
    EncoderError,
)

from backend.services.asset_gen import (
    # Service
    AssetGenService,
    AssetGenConfig,
    # Types
    LLMProvider as AssetGenLLMProvider,
    ThumbnailMode,
    SummaryStyle,
    TargetPlatform,
    LLMInstance as AssetGenLLMInstance,
    ImageGenInstance,
    TitleConfig,
    SummaryConfig,
    ThumbnailConfig,
    # Utilities
    SubtitleExtractor,
    LLMInstanceManager as AssetGenLLMManager,
    TitleGenerator,
    SummaryGenerator,
    ThumbnailGenerator,
    # Exceptions
    AssetGenError,
    SubtitleNotFoundError,
    LLMError as AssetGenLLMError,
    AllInstancesFailedError as AssetGenAllInstancesFailedError,
    ThumbnailError,
    FFmpegError as AssetGenFFmpegError,
)

from backend.services.editor import (
    # Service
    EditorService,
    EditorConfig,
    # Types
    ClipMode,
    OperationType,
    PreviewQuality,
    SplitPoint,
    SegmentInfo,
    ClipConfig,
    SplitConfig,
    # Utilities
    SubtitleProcessor,
    FFmpegProgressParser as EditorFFmpegProgressParser,
    VideoClipper,
    VideoSplitter,
    # Exceptions
    EditorError,
    VideoNotFoundError,
    InvalidTimeRangeError,
    FFmpegError as EditorFFmpegError,
    SubtitleError,
    DiskSpaceError,
)


__all__ = [
    # Download Service
    "DownloadService",
    "DownloadConfig",
    # Download Types
    "DownloadChannel",
    "VideoQuality",
    # Download Utilities
    "URLParser",
    "ProgressParser",
    "DirectoryManager",
    "MetadataExtractor",
    # Download Exceptions
    "DownloadError",
    "UnsupportedURLError",
    "ChannelIncompatibleError",
    "DuplicateVideoError",
    "DownloadFailedError",
    # Media Service
    "MediaService",
    "MediaConfig",
    # Media Types
    "VideoFilter",
    "FileScanner",
    # Media Constants
    "FILE_PATTERNS",
    "AUTO_TAG_RULES",
    "FILE_AUTO_TAGS",
    "TAG_COLORS",
    # ASR Service
    "ASRService",
    "ASRConfig",
    # ASR Types
    "ASRChannel",
    "WhisperModel",
    "ComputeType",
    # ASR Utilities
    "AudioExtractor",
    "WhisperTranscriber",
    "SRTGenerator",
    "SRTSegment",
    "OpenAITranscriber",
    "GeminiTranscriber",
    # ASR Exceptions
    "ASRError",
    "AudioExtractionError",
    "ModelLoadError",
    "TranscriptionError",
    "APIError",
    # Translation Service
    "TranslationService",
    "TranslationConfig",
    # Translation Types
    "LLMProvider",
    "Language",
    "SRTEntry",
    "LLMInstance",
    # Translation Utilities
    "SRTParser",
    "LLMInstanceManager",
    "BatchProcessor",
    # Translation Providers
    "DeepSeekProvider",
    "TranslatorOpenAIProvider",
    "TranslatorGeminiProvider",
    # Translation Exceptions
    "TranslationError",
    "SRTParseError",
    "LLMError",
    "AllInstancesFailedError",
    "ResultMismatchError",
    # TTS Service
    "TTSService",
    "TTSConfig",
    # TTS Types
    "TTSEngine",
    "OutputFormat",
    "SubtitleEntry",
    "AudioSegment",
    # TTS Engines
    "BaseTTSEngine",
    "ChatTTSEngine",
    "CoquiTTSEngine",
    "VITSEngine",
    # TTS Utilities
    "SpeedCalculator",
    "TextSplitter",
    "AudioProcessor",
    # TTS Exceptions
    "TTSError",
    "EngineLoadError",
    "SynthesisError",
    "AudioProcessError",
    # Synthesizer Service
    "SynthesizerService",
    "SynthesizerConfig",
    # Synthesizer Types
    "SubtitleMode",
    "VideoCodec",
    "HardwareAccel",
    "SubtitlePosition",
    "SubtitleStyle",
    "StylePreset",
    # Synthesizer Utilities
    "FFmpegCommandBuilder",
    "FFmpegProgressParser",
    # Synthesizer Constants
    "DEFAULT_PRESETS",
    # Synthesizer Exceptions
    "SynthesizerError",
    "FFmpegError",
    "InputFileError",
    "EncoderError",
    # Asset Generation Service
    "AssetGenService",
    "AssetGenConfig",
    # Asset Generation Types
    "AssetGenLLMProvider",
    "ThumbnailMode",
    "SummaryStyle",
    "TargetPlatform",
    "AssetGenLLMInstance",
    "ImageGenInstance",
    "TitleConfig",
    "SummaryConfig",
    "ThumbnailConfig",
    # Asset Generation Utilities
    "SubtitleExtractor",
    "AssetGenLLMManager",
    "TitleGenerator",
    "SummaryGenerator",
    "ThumbnailGenerator",
    # Asset Generation Exceptions
    "AssetGenError",
    "SubtitleNotFoundError",
    "AssetGenLLMError",
    "AssetGenAllInstancesFailedError",
    "ThumbnailError",
    "AssetGenFFmpegError",
    # Editor Service
    "EditorService",
    "EditorConfig",
    # Editor Types
    "ClipMode",
    "OperationType",
    "PreviewQuality",
    "SplitPoint",
    "SegmentInfo",
    "ClipConfig",
    "SplitConfig",
    # Editor Utilities
    "SubtitleProcessor",
    "EditorFFmpegProgressParser",
    "VideoClipper",
    "VideoSplitter",
    # Editor Exceptions
    "EditorError",
    "VideoNotFoundError",
    "InvalidTimeRangeError",
    "EditorFFmpegError",
    "SubtitleError",
    "DiskSpaceError",
]
