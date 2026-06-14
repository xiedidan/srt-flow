"""
FastAPI application entry point.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.routers import api_router, ws_router
from backend.app.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from backend.app.schemas import success_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    from backend.core import (
        get_config_manager, 
        get_system_settings, 
        init_database, 
        close_database,
        init_logger,
        get_logger,
    )
    
    # Initialize configuration
    config = get_config_manager()
    settings = get_system_settings()
    
    # Ensure data directories exist
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.downloads_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    
    # Initialize logger
    init_logger(
        log_dir=settings.log_dir,
        log_level=settings.log_level,
        enable_console=True,
        enable_color=settings.debug,
    )
    logger = get_logger("srtflow")
    
    logger.info("SRT Flow backend starting...")
    logger.info(f"Configuration loaded (data_dir: {settings.data_dir})")
    logger.info("Data directories initialized")
    
    # Initialize database
    db = await init_database()
    logger.info(f"Database initialized ({settings.database_path})")
    
    # Initialize task queue and workers
    from backend.core.database import get_database_manager
    from backend.workers.queue import QueueManager
    from backend.workers.worker import WorkerManager
    from backend.workers.scheduler import Scheduler
    from backend.services.download import DownloadService, DownloadConfig
    from backend.services.asr import ASRService, ASRConfig
    from backend.services.translator import TranslationService, TranslationConfig
    from backend.services.tts import TTSService, TTSConfig
    from backend.services.synthesizer import SynthesizerService, SynthesizerConfig
    from backend.services.asset_gen import AssetGenService, AssetGenConfig
    from backend.services.editor import EditorService, EditorConfig
    from backend.core.models import TaskType
    
    db_manager = get_database_manager()
    
    # Create a session for workers
    async with db_manager.session() as session:
        queue_manager = QueueManager(session)
        
        # Recover interrupted tasks
        recovered = await queue_manager.recover_interrupted_tasks()
        if recovered:
            logger.info(f"Recovered {len(recovered)} interrupted tasks")
    
    # Create worker manager with fresh session per task
    worker_manager = WorkerManager.__new__(WorkerManager)
    worker_manager._queue = None  # Will be set per-task
    worker_manager._poll_interval = 2.0
    worker_manager._shutdown_timeout = 30.0
    worker_manager._workers = {}
    worker_manager._services = {}
    worker_manager._tasks = {}
    worker_manager._running = False
    worker_manager._logger = get_logger("worker_manager")
    
    # Register download service
    download_config = DownloadConfig()
    download_service = DownloadService(download_config, download_dir=settings.downloads_dir)
    worker_manager._services[TaskType.DOWNLOAD] = download_service
    
    # Register ASR service
    asr_config = ASRConfig(model_cache_dir=str(Path(settings.data_dir) / "models"))
    asr_service = ASRService(asr_config)
    worker_manager._services[TaskType.ASR] = asr_service
    
    # Register Translation service
    translation_config = TranslationConfig()
    translation_service = TranslationService(translation_config)
    worker_manager._services[TaskType.TRANSLATE] = translation_service
    
    # Register TTS service
    tts_config = TTSConfig()
    tts_service = TTSService(tts_config)
    worker_manager._services[TaskType.TTS] = tts_service
    
    # Register Synthesizer service
    synthesizer_config = SynthesizerConfig()
    synthesizer_service = SynthesizerService(synthesizer_config)
    worker_manager._services[TaskType.SYNTHESIZE] = synthesizer_service
    
    # Register Asset Generation service
    asset_gen_config = AssetGenConfig()
    asset_gen_service = AssetGenService(asset_gen_config)
    worker_manager._services[TaskType.ASSET_GEN] = asset_gen_service
    
    # Register Editor service
    editor_config = EditorConfig()
    editor_service = EditorService(editor_config)
    worker_manager._services[TaskType.EDITOR] = editor_service
    
    # Start parallel worker loops in background
    import asyncio
    
    # Task types and their services
    task_types = [
        TaskType.DOWNLOAD, 
        TaskType.ASR, 
        TaskType.TRANSLATE,
        TaskType.TTS,
        TaskType.SYNTHESIZE,
        TaskType.ASSET_GEN,
        TaskType.EDITOR,
    ]
    services = {
        TaskType.DOWNLOAD: download_service,
        TaskType.ASR: asr_service,
        TaskType.TRANSLATE: translation_service,
        TaskType.TTS: tts_service,
        TaskType.SYNTHESIZE: synthesizer_service,
        TaskType.ASSET_GEN: asset_gen_service,
        TaskType.EDITOR: editor_service,
    }
    
    # Track running tasks per type to enforce concurrency limit (1 per type)
    running_tasks: Dict[TaskType, bool] = {t: False for t in task_types}
    running_tasks_lock = asyncio.Lock()
    
    async def update_progress(task_id: str, progress: int):
        """Broadcast task progress via WebSocket (no DB update for performance)."""
        try:
            from backend.app.routers.websocket import broadcast_task_progress
            await broadcast_task_progress(task_id, progress)
        except Exception as e:
            pass  # Silently ignore progress broadcast errors

    async def process_task_type(task_type: TaskType, service):
        """
        Worker loop for a specific task type.
        Each task type runs in its own coroutine, enabling parallel processing
        of different task types (pipeline mode).
        """
        worker_logger = get_logger(f"worker.{task_type.value}")
        worker_logger.info(f"Worker for {task_type.value} started")
        
        while True:
            try:
                # Check if this type already has a running task
                async with running_tasks_lock:
                    if running_tasks[task_type]:
                        await asyncio.sleep(1)
                        continue
                
                async with db_manager.session() as session:
                    queue = QueueManager(session)
                    task = await queue.dequeue(task_type)
                    
                    if not task:
                        await asyncio.sleep(2)
                        continue
                    
                    # Debug: log dequeue result
                    worker_logger.info(f"Dequeued task: {task.id}")
                    
                    # Mark this type as running
                    async with running_tasks_lock:
                        running_tasks[task_type] = True
                    
                    try:
                        worker_logger.info(f"Processing {task_type.value} task: {task.id}")
                        
                        # Start task
                        await queue.start_task(task.id)
                        await session.commit()
                        
                        # Broadcast task started via WebSocket
                        from backend.app.routers.websocket import broadcast_task_update
                        await broadcast_task_update(
                            task_id=task.id,
                            task_type=task_type.value,
                            status="running",
                            video_id=task.video_id,
                        )
                        
                        # Pre-processing: resolve video_path for ASR tasks
                        if task_type == TaskType.ASR:
                            from backend.core.repositories import VideoRepository
                            
                            video_id = task.payload.get("video_id") if task.payload else None
                            if video_id and not task.payload.get("video_path"):
                                video_repo = VideoRepository(session)
                                video = await video_repo.get_by_id(video_id)
                                if video and video.directory_path:
                                    video_dir = Path(video.directory_path)
                                    video_file = None
                                    for ext in [".mp4", ".mkv", ".webm", ".avi", ".mov"]:
                                        candidate = video_dir / f"video{ext}"
                                        if candidate.exists():
                                            video_file = candidate
                                            break
                                    if not video_file:
                                        for f in video_dir.iterdir():
                                            if f.suffix.lower() in [".mp4", ".mkv", ".webm", ".avi", ".mov"]:
                                                video_file = f
                                                break
                                    
                                    if video_file:
                                        task.payload["video_path"] = str(video_file)
                                        worker_logger.info(f"Resolved video_path: {video_file}")
                                    else:
                                        raise Exception(f"No video file found in {video_dir}")
                                else:
                                    raise Exception(f"Video not found: {video_id}")
                        
                        # Load config from database for download tasks
                        if task_type == TaskType.DOWNLOAD:
                            from backend.core import get_config_manager
                            config_mgr = get_config_manager()
                            config_mgr.set_db_session(session)
                            try:
                                db_config = await config_mgr.get_config("download", use_cache=False)
                                global_config = await config_mgr.get_config("global", use_cache=False)
                                
                                cookies_browser_raw = getattr(db_config, 'cookies_browser', None)
                                if cookies_browser_raw:
                                    cookies_browser_str = cookies_browser_raw.value if hasattr(cookies_browser_raw, 'value') else str(cookies_browser_raw)
                                    download_service._yt_dlp._config.cookies_browser = cookies_browser_str
                                else:
                                    download_service._yt_dlp._config.cookies_browser = None
                                
                                use_proxy = task.payload.get('use_proxy', True) if task.payload else True
                                if use_proxy:
                                    download_service._yt_dlp._config.proxy_url = getattr(global_config, 'proxy_url', None)
                                else:
                                    download_service._yt_dlp._config.proxy_url = None
                                
                                download_service._yt_dlp._config.download_subtitles = getattr(db_config, 'download_subtitles', True)
                                download_service._yt_dlp._config.nodejs_path = getattr(db_config, 'nodejs_path', None)
                                
                                worker_logger.info(f"Download config: cookies_browser={download_service._yt_dlp._config.cookies_browser}")
                            except Exception as e:
                                import traceback
                                worker_logger.warning(f"Failed to load download config: {e}\n{traceback.format_exc()}")
                        
                        # Load config from database for ASR tasks
                        if task_type == TaskType.ASR:
                            from backend.core import get_config_manager
                            config_mgr = get_config_manager()
                            config_mgr.set_db_session(session)
                            try:
                                asr_db_config = await config_mgr.get_config("asr", use_cache=False)
                                global_config = await config_mgr.get_config("global", use_cache=False)
                                
                                gemini_api_key = None
                                gemini_base_url = asr_db_config.gemini_base_url
                                
                                if asr_db_config.engine.value == "gemini":
                                    gemini_provider_id = getattr(asr_db_config, 'gemini_provider_id', None)
                                    if gemini_provider_id:
                                        from backend.core.repositories import AIProviderRepository
                                        from backend.core.encryption import get_encryption_manager
                                        
                                        ai_repo = AIProviderRepository(session)
                                        ai_provider = await ai_repo.get_by_id(gemini_provider_id)
                                        
                                        if ai_provider and ai_provider.is_enabled:
                                            encryption = get_encryption_manager(config_mgr.system.data_dir)
                                            try:
                                                gemini_api_key = encryption.decrypt(ai_provider.api_key)
                                                if ai_provider.base_url:
                                                    gemini_base_url = ai_provider.base_url
                                                worker_logger.info(f"Loaded Gemini API key from AI Provider: {ai_provider.name}")
                                            except Exception as decrypt_err:
                                                worker_logger.warning(f"Failed to decrypt AI Provider key: {decrypt_err}")
                                    
                                    if not gemini_api_key:
                                        gemini_api_key = await config_mgr.get_api_key("asr", "gemini_api_key")
                                
                                if not task.payload:
                                    task.payload = {}
                                task.payload["_db_config"] = {
                                    "engine": asr_db_config.engine.value,
                                    "model_size": asr_db_config.whisper_model_size.value,
                                    "device": asr_db_config.device.value,
                                    "extra_args": asr_db_config.whisper_extra_args,
                                    "gemini_api_key": gemini_api_key,
                                    "gemini_base_url": gemini_base_url,
                                }
                                
                                if not task.payload.get("language") or task.payload.get("language") == "auto":
                                    if global_config and global_config.default_source_language:
                                        task.payload["_default_language"] = global_config.default_source_language
                                
                                worker_logger.info(f"ASR config loaded: engine={asr_db_config.engine.value}")
                            except Exception as e:
                                import traceback
                                worker_logger.warning(f"Failed to load ASR config: {e}\n{traceback.format_exc()}")

                        # Pre-processing for TRANSLATE tasks
                        if task_type == TaskType.TRANSLATE:
                            from backend.core.repositories import VideoRepository
                            from backend.services.translator import LLMInstance, LLMProvider
                            
                            video_id = task.payload.get("video_id") if task.payload else None
                            if video_id and not task.payload.get("subtitle_path"):
                                video_repo = VideoRepository(session)
                                video = await video_repo.get_by_id(video_id)
                                if video and video.directory_path:
                                    video_dir = Path(video.directory_path)
                                    subtitle_file = video_dir / "subtitle_original.srt"
                                    
                                    if subtitle_file.exists():
                                        task.payload["subtitle_path"] = str(subtitle_file)
                                        task.payload["video_title"] = video.title
                                        task.payload["channel_name"] = video.channel_name
                                        worker_logger.info(f"Resolved subtitle_path: {subtitle_file}")
                                    else:
                                        raise Exception(f"Subtitle file not found: {subtitle_file}")
                                else:
                                    raise Exception(f"Video not found: {video_id}")
                            
                            from backend.core import get_config_manager
                            config_mgr = get_config_manager()
                            config_mgr.set_db_session(session)
                            try:
                                translate_db_config = await config_mgr.get_config("translate", use_cache=False)
                                global_config = await config_mgr.get_config("global", use_cache=False)
                                
                                if not task.payload.get("target_language"):
                                    task.payload["target_language"] = getattr(global_config, 'default_target_language', 'zh-CN')
                                
                                if not task.payload.get("source_language"):
                                    task.payload["source_language"] = getattr(global_config, 'default_source_language', 'auto')
                                
                                llm_instances = []
                                ai_provider_id = getattr(translate_db_config, 'ai_provider_id', None)
                                if ai_provider_id:
                                    from backend.core.repositories import AIProviderRepository
                                    from backend.core.encryption import get_encryption_manager
                                    
                                    ai_repo = AIProviderRepository(session)
                                    ai_provider = await ai_repo.get_by_id(ai_provider_id)
                                    
                                    if ai_provider and ai_provider.is_enabled:
                                        encryption = get_encryption_manager(config_mgr.system.data_dir)
                                        try:
                                            api_key = encryption.decrypt(ai_provider.api_key)
                                        except Exception:
                                            api_key = None
                                        
                                        if api_key:
                                            base_url = ai_provider.base_url
                                            if not base_url:
                                                default_urls = {
                                                    "deepseek": "https://api.deepseek.com/v1",
                                                    "openai": "https://api.openai.com/v1",
                                                    "gemini": "https://generativelanguage.googleapis.com/v1beta",
                                                }
                                                base_url = default_urls.get(ai_provider.api_type.value, "")
                                            
                                            model = getattr(translate_db_config, 'model_name', None) or "deepseek-chat"
                                            temperature = getattr(translate_db_config, 'temperature', 1.0)
                                            
                                            llm_instances.append(LLMInstance(
                                                name=ai_provider.name,
                                                provider=LLMProvider(ai_provider.api_type.value),
                                                api_key=api_key,
                                                base_url=base_url,
                                                model=model,
                                                temperature=temperature,
                                                priority=100,
                                            ))
                                            worker_logger.info(f"Loaded AI Provider: {ai_provider.name}, model: {model}")
                                
                                if not llm_instances:
                                    worker_logger.warning("No AI Provider configured for translation")
                                
                                translation_service._config.llm_instances = llm_instances
                                translation_service._config.batch_size = getattr(translate_db_config, 'batch_size', 30)
                                translation_service._config.max_retries_per_instance = getattr(translate_db_config, 'max_retries', 3)
                                translation_service._config.system_prompt = getattr(translate_db_config, 'system_prompt', None)
                                translation_service._config.user_prompt_template = getattr(translate_db_config, 'user_prompt_template', None)
                                translation_service._config.task_context = task.payload.get('task_context', None)
                                translation_service._config.context_overlap_lines = getattr(translate_db_config, 'context_overlap_lines', 3)
                                translation_service._config.empty_line_threshold = getattr(translate_db_config, 'empty_line_threshold', 0.3)
                                
                                translation_service._instance_manager = None
                                translation_service._batch_processor = None
                                
                                worker_logger.info(f"Translation config loaded: {len(llm_instances)} LLM instances")
                            except Exception as e:
                                import traceback
                                worker_logger.warning(f"Failed to load translation config: {e}\n{traceback.format_exc()}")

                        # Pre-processing for TTS tasks
                        if task_type == TaskType.TTS:
                            from backend.core.repositories import VideoRepository
                            from backend.services.tts import TTSEngine
                            
                            video_id = task.payload.get("video_id") if task.payload else None
                            if video_id and not task.payload.get("subtitle_path"):
                                video_repo = VideoRepository(session)
                                video = await video_repo.get_by_id(video_id)
                                if video and video.directory_path:
                                    video_dir = Path(video.directory_path)
                                    subtitle_file = video_dir / "subtitle_translated.srt"
                                    if not subtitle_file.exists():
                                        subtitle_file = video_dir / "subtitle_original.srt"
                                    
                                    if subtitle_file.exists():
                                        task.payload["subtitle_path"] = str(subtitle_file)
                                        worker_logger.info(f"Resolved TTS subtitle_path: {subtitle_file}")
                                    else:
                                        raise Exception(f"No subtitle file found in {video_dir}")
                                else:
                                    raise Exception(f"Video not found: {video_id}")
                            
                            from backend.core import get_config_manager
                            config_mgr = get_config_manager()
                            config_mgr.set_db_session(session)
                            try:
                                tts_db_config = await config_mgr.get_config("tts", use_cache=False)
                                
                                engine = getattr(tts_db_config, 'engine', None)
                                if engine:
                                    engine_value = engine.value if hasattr(engine, 'value') else str(engine)
                                    tts_service._config.engine = TTSEngine(engine_value)
                                
                                tts_service._config.use_gpu = getattr(tts_db_config, 'use_gpu', True)
                                tts_service._config.reference_audio = getattr(tts_db_config, 'reference_audio', None)
                                
                                output_format = getattr(tts_db_config, 'output_format', None)
                                if output_format:
                                    from backend.services.tts import OutputFormat
                                    tts_service._config.output_format = OutputFormat(output_format.value if hasattr(output_format, 'value') else str(output_format))
                                
                                speed_factor = getattr(tts_db_config, 'speed_factor', None)
                                if speed_factor:
                                    tts_service._config.base_chars_per_second = 4.0 / speed_factor
                                
                                tts_service._config.chattts_temperature = getattr(tts_db_config, 'chattts_temperature', 0.3)
                                tts_service._config.chattts_top_p = getattr(tts_db_config, 'chattts_top_p', 0.7)
                                tts_service._config.chattts_top_k = getattr(tts_db_config, 'chattts_top_k', 20)
                                
                                tts_service._config.indextts_mode = getattr(tts_db_config, 'indextts_mode', 'local')
                                tts_service._config.indextts_api_url = getattr(tts_db_config, 'indextts_api_url', None)
                                
                                tts_service._config.sparktts_mode = getattr(tts_db_config, 'sparktts_mode', 'local')
                                tts_service._config.sparktts_api_url = getattr(tts_db_config, 'sparktts_api_url', None)
                                
                                tts_service._config.cozyvoice_mode = getattr(tts_db_config, 'cozyvoice_mode', 'local')
                                tts_service._config.cozyvoice_api_url = getattr(tts_db_config, 'cozyvoice_api_url', None)
                                tts_service._config.cozyvoice_speaker = getattr(tts_db_config, 'cozyvoice_speaker', '中文女')
                                
                                tts_service._config.coqui_model_name = getattr(tts_db_config, 'coqui_model_name', 'tts_models/multilingual/multi-dataset/xtts_v2')
                                tts_service._config.vits_model_path = getattr(tts_db_config, 'vits_model_path', None)
                                
                                # Load proxy from global config for online TTS services
                                global_config = await config_mgr.get_config("global", use_cache=False)
                                tts_service._config.proxy_url = getattr(global_config, 'proxy_url', None)
                                
                                tts_service._config.enable_sentence_merge = getattr(tts_db_config, 'enable_sentence_merge', False)
                                tts_service._config.sentence_merge_model = getattr(tts_db_config, 'sentence_merge_model', 'deepseek-chat')
                                tts_service._config.sentence_merge_temperature = getattr(tts_db_config, 'sentence_merge_temperature', 0.3)
                                tts_service._config.sentence_merge_system_prompt = getattr(tts_db_config, 'sentence_merge_system_prompt', None)
                                tts_service._config.sentence_merge_user_prompt = getattr(tts_db_config, 'sentence_merge_user_prompt', None)
                                
                                sentence_merge_provider_id = getattr(tts_db_config, 'sentence_merge_provider_id', None)
                                if tts_service._config.enable_sentence_merge and sentence_merge_provider_id:
                                    from backend.core.repositories import AIProviderRepository
                                    from backend.core.encryption import get_encryption_manager
                                    from backend.core.config import get_system_settings
                                    
                                    ai_repo = AIProviderRepository(session)
                                    provider = await ai_repo.get_by_id(sentence_merge_provider_id)
                                    
                                    if provider and provider.is_enabled:
                                        settings = get_system_settings()
                                        encryption = get_encryption_manager(settings.data_dir)
                                        
                                        try:
                                            api_key = encryption.decrypt(provider.api_key)
                                            base_url = provider.base_url or {
                                                'deepseek': 'https://api.deepseek.com/v1',
                                                'openai': 'https://api.openai.com/v1',
                                                'openai_compatible': provider.base_url,
                                            }.get(provider.api_type.value, 'https://api.deepseek.com/v1')
                                            
                                            task.payload["sentence_merge_api_key"] = api_key
                                            task.payload["sentence_merge_base_url"] = base_url
                                            worker_logger.info(f"Sentence merge AI provider loaded: {provider.name}")
                                        except Exception as e:
                                            worker_logger.warning(f"Failed to decrypt sentence merge API key: {e}")
                                
                                worker_logger.info(f"TTS config loaded: engine={tts_service._config.engine.value}")
                                
                                reference_audio_id = task.payload.get("reference_audio_id") if task.payload else None
                                if reference_audio_id:
                                    from backend.core.repositories import ReferenceAudioRepository
                                    ref_audio_repo = ReferenceAudioRepository(session)
                                    ref_audio = await ref_audio_repo.get_by_id(reference_audio_id)
                                    if ref_audio and ref_audio.file_path:
                                        task.payload["speaker"] = ref_audio.file_path
                                        worker_logger.info(f"Resolved reference audio: {ref_audio.original_filename}")
                                
                            except Exception as e:
                                import traceback
                                worker_logger.warning(f"Failed to load TTS config: {e}\n{traceback.format_exc()}")

                        # Pre-processing for SYNTHESIZE tasks
                        if task_type == TaskType.SYNTHESIZE:
                            from backend.core.repositories import VideoRepository
                            from backend.core import get_config_manager
                            config_mgr = get_config_manager()
                            config_mgr.set_db_session(session)
                            
                            video_id = task.payload.get("video_id") if task.payload else None
                            if video_id:
                                video_repo = VideoRepository(session)
                                video = await video_repo.get_by_id(video_id)
                                if video and video.directory_path:
                                    video_dir = Path(video.directory_path)
                                    
                                    def convert_path(p: Path) -> str:
                                        """Convert WSL path to Windows absolute path."""
                                        path_str = str(p)
                                        if path_str.startswith("/mnt/"):
                                            drive = path_str[5].upper()
                                            rest = path_str[7:]
                                            return drive + ":/" + rest
                                        elif path_str.startswith("/project/"):
                                            return "E:/" + path_str[1:]
                                        elif path_str.startswith("/app/"):
                                            return "E:/project/srt-flow/" + path_str[5:]
                                        elif not path_str.startswith("/") and not path_str.startswith("E:"):
                                            # Relative path - resolve to absolute path
                                            resolved = Path(path_str).resolve()
                                            return str(resolved).replace("\\", "/")
                                        return path_str
                                    
                                    if not task.payload.get("video_path"):
                                        for ext in [".mp4", ".mkv", ".webm"]:
                                            candidate = video_dir / f"video{ext}"
                                            if candidate.exists():
                                                task.payload["video_path"] = convert_path(candidate)
                                                break
                                    
                                    if not task.payload.get("tts_audio_path"):
                                        tts_audio = video_dir / "audio_tts.m4a"
                                        if tts_audio.exists():
                                            task.payload["tts_audio_path"] = convert_path(tts_audio)
                                    
                                    if not task.payload.get("original_subtitle_path"):
                                        original_sub = video_dir / "subtitle_original.srt"
                                        if original_sub.exists():
                                            task.payload["original_subtitle_path"] = convert_path(original_sub)
                                    
                                    if not task.payload.get("translated_subtitle_path"):
                                        translated_sub = video_dir / "subtitle_translated.srt"
                                        if translated_sub.exists():
                                            task.payload["translated_subtitle_path"] = convert_path(translated_sub)
                                    
                                    worker_logger.info(f"Resolved synthesize paths for video: {video_id}")
                                else:
                                    raise Exception(f"Video not found: {video_id}")
                            
                            try:
                                synthesis_db_config = await config_mgr.get_config("synthesis", use_cache=False)
                                
                                if not task.payload.get("video_encoder"):
                                    task.payload["video_encoder"] = synthesis_db_config.video_encoder.value
                                if not task.payload.get("video_crf"):
                                    task.payload["video_crf"] = synthesis_db_config.video_crf
                                if not task.payload.get("video_preset"):
                                    task.payload["video_preset"] = synthesis_db_config.video_preset
                                
                                if not task.payload.get("primary_subtitle_style"):
                                    task.payload["primary_subtitle_style"] = {
                                        "font_name": synthesis_db_config.translated_subtitle_font,
                                        "font_size": synthesis_db_config.translated_subtitle_font_size,
                                        "font_bold": synthesis_db_config.translated_subtitle_bold,
                                        "font_color": synthesis_db_config.translated_subtitle_color,
                                        "font_alpha": synthesis_db_config.translated_subtitle_alpha,
                                        "outline_color": synthesis_db_config.translated_subtitle_outline_color,
                                        "outline_width": synthesis_db_config.translated_subtitle_outline_width,
                                        "shadow_enabled": synthesis_db_config.translated_subtitle_shadow_enabled,
                                        "shadow_offset": synthesis_db_config.translated_subtitle_shadow_offset,
                                        "position": synthesis_db_config.translated_subtitle_position.value,
                                        "margin_v": synthesis_db_config.translated_subtitle_margin_v,
                                        "background_enabled": synthesis_db_config.translated_subtitle_background_enabled,
                                        "background_color": synthesis_db_config.translated_subtitle_background_color,
                                        "background_alpha": synthesis_db_config.translated_subtitle_background_alpha,
                                    }
                                
                                if not task.payload.get("secondary_subtitle_style"):
                                    task.payload["secondary_subtitle_style"] = {
                                        "font_name": synthesis_db_config.original_subtitle_font,
                                        "font_size": synthesis_db_config.original_subtitle_font_size,
                                        "font_bold": synthesis_db_config.original_subtitle_bold,
                                        "font_color": synthesis_db_config.original_subtitle_color,
                                        "font_alpha": synthesis_db_config.original_subtitle_alpha,
                                        "outline_color": synthesis_db_config.original_subtitle_outline_color,
                                        "outline_width": synthesis_db_config.original_subtitle_outline_width,
                                        "shadow_enabled": synthesis_db_config.original_subtitle_shadow_enabled,
                                        "shadow_offset": synthesis_db_config.original_subtitle_shadow_offset,
                                        "position": synthesis_db_config.original_subtitle_position.value,
                                        "margin_v": synthesis_db_config.original_subtitle_margin_v,
                                        "background_enabled": synthesis_db_config.original_subtitle_background_enabled,
                                        "background_color": synthesis_db_config.original_subtitle_background_color,
                                        "background_alpha": synthesis_db_config.original_subtitle_background_alpha,
                                    }
                                
                                worker_logger.info(f"Loaded synthesis subtitle styles from config")
                            except Exception as e:
                                import traceback
                                worker_logger.warning(f"Failed to load synthesis config: {e}\n{traceback.format_exc()}")

                        # Pre-processing for ASSET_GEN tasks
                        if task_type == TaskType.ASSET_GEN:
                            from backend.core.repositories import VideoRepository
                            from backend.services.asset_gen import (
                                LLMInstance as AssetGenLLMInstance,
                                LLMProvider as AssetGenLLMProvider,
                            )
                            from backend.core.encryption import get_encryption_manager
                            from backend.core.config import get_system_settings
                            
                            video_id = task.payload.get("video_id") if task.payload else None
                            if video_id:
                                video_repo = VideoRepository(session)
                                video = await video_repo.get_by_id(video_id)
                                if video and video.directory_path:
                                    video_dir = Path(video.directory_path)
                                    task.payload["video_dir"] = str(video_dir)
                                    task.payload["video_title"] = video.title
                                    task.payload["channel_name"] = video.channel_name
                                    
                                    if not task.payload.get("video_path"):
                                        video_file = None
                                        for ext in [".mp4", ".mkv", ".webm", ".avi", ".mov"]:
                                            candidate = video_dir / f"video{ext}"
                                            if candidate.exists():
                                                video_file = candidate
                                                break
                                        if not video_file:
                                            for f in video_dir.iterdir():
                                                if f.suffix.lower() in [".mp4", ".mkv", ".webm", ".avi", ".mov"]:
                                                    video_file = f
                                                    break
                                        
                                        if video_file:
                                            task.payload["video_path"] = str(video_file)
                                        else:
                                            raise Exception(f"No video file found in {video_dir}")
                                    
                                    if not task.payload.get("subtitle_path"):
                                        for sub_name in ["subtitle_translated.srt", "subtitle_original.srt"]:
                                            sub_file = video_dir / sub_name
                                            if sub_file.exists():
                                                task.payload["subtitle_path"] = str(sub_file)
                                                break
                                    
                                    worker_logger.info(f"Resolved asset_gen paths for video: {video_id}")
                                else:
                                    raise Exception(f"Video not found: {video_id}")
                            
                            from backend.core import get_config_manager
                            from backend.core.repositories import AIProviderRepository
                            config_mgr = get_config_manager()
                            config_mgr.set_db_session(session)
                            try:
                                asset_db_config = await config_mgr.get_config("asset", use_cache=False)
                                ai_provider_repo = AIProviderRepository(session)
                                encryption = get_encryption_manager(get_system_settings().data_dir)
                                
                                async def load_llm_from_provider(provider_id, model_name, temperature, name_prefix):
                                    if not provider_id:
                                        return None
                                    provider = await ai_provider_repo.get_by_id(provider_id)
                                    if not provider or not provider.is_enabled:
                                        return None
                                    try:
                                        api_key = encryption.decrypt(provider.api_key)
                                        provider_type = provider.api_type.value
                                        base_url = provider.base_url or ""
                                        
                                        if not base_url:
                                            if provider_type == "deepseek":
                                                base_url = "https://api.deepseek.com/v1"
                                            elif provider_type == "openai":
                                                base_url = "https://api.openai.com/v1"
                                            elif provider_type == "gemini":
                                                base_url = "https://generativelanguage.googleapis.com/v1beta"
                                        
                                        return AssetGenLLMInstance(
                                            name=f"{name_prefix}_{provider_type}",
                                            provider=AssetGenLLMProvider(provider_type),
                                            api_key=api_key,
                                            base_url=base_url,
                                            model=model_name,
                                            temperature=temperature,
                                            priority=100,
                                        )
                                    except Exception as e:
                                        worker_logger.warning(f"Failed to load provider {provider_id}: {e}")
                                        return None
                                
                                llm_instances = []
                                
                                title_provider_id = getattr(asset_db_config, 'title_ai_provider_id', None)
                                title_model = getattr(asset_db_config, 'title_model_name', 'deepseek-chat')
                                title_temp = getattr(asset_db_config, 'title_temperature', 0.85)
                                title_instance = await load_llm_from_provider(title_provider_id, title_model, title_temp, "title")
                                if title_instance:
                                    llm_instances.append(title_instance)
                                
                                summary_provider_id = getattr(asset_db_config, 'summary_ai_provider_id', None)
                                summary_model = getattr(asset_db_config, 'summary_model_name', 'deepseek-chat')
                                summary_temp = getattr(asset_db_config, 'summary_temperature', 0.65)
                                summary_instance = await load_llm_from_provider(summary_provider_id, summary_model, summary_temp, "summary")
                                if summary_instance:
                                    if not title_instance or summary_provider_id != title_provider_id:
                                        llm_instances.append(summary_instance)
                                
                                thumbnail_provider_id = getattr(asset_db_config, 'thumbnail_ai_provider_id', None)
                                thumbnail_model = getattr(asset_db_config, 'thumbnail_model_name', 'deepseek-chat')
                                thumbnail_temp = getattr(asset_db_config, 'thumbnail_temperature', 0.7)
                                thumbnail_instance = await load_llm_from_provider(thumbnail_provider_id, thumbnail_model, thumbnail_temp, "thumbnail")
                                
                                asset_gen_service._config.llm_instances = llm_instances
                                if thumbnail_instance:
                                    asset_gen_service._config.thumbnail_llm_instance = thumbnail_instance
                                
                                from backend.services.asset_gen import ImageGenInstance
                                image_provider = getattr(asset_db_config, 'thumbnail_image_provider', 'dall-e')
                                image_api_key = await config_mgr.get_api_key("asset", "thumbnail_image_api_key")
                                image_base_url = getattr(asset_db_config, 'thumbnail_image_base_url', None)
                                image_model = getattr(asset_db_config, 'thumbnail_image_model', 'dall-e-3')
                                
                                if image_api_key:
                                    if not image_base_url and image_provider == "dall-e":
                                        image_base_url = "https://api.openai.com/v1"
                                    
                                    asset_gen_service._config.image_gen_instance = ImageGenInstance(
                                        name=f"thumbnail_{image_provider}",
                                        provider=image_provider,
                                        api_key=image_api_key,
                                        base_url=image_base_url or "",
                                        model=image_model,
                                    )
                                
                                asset_gen_service._llm_manager = None
                                asset_gen_service._title_generator = None
                                asset_gen_service._summary_generator = None
                                asset_gen_service._thumbnail_generator = None
                                
                                worker_logger.info(f"Asset gen config loaded: {len(llm_instances)} LLM instances")
                            except Exception as e:
                                import traceback
                                worker_logger.warning(f"Failed to load asset_gen config: {e}\n{traceback.format_exc()}")

                        # Execute task
                        loop = asyncio.get_event_loop()
                        def progress_cb(p):
                            asyncio.run_coroutine_threadsafe(update_progress(task.id, p), loop)
                        
                        result = await service.execute(task, progress_cb)
                        
                        # Post-processing for download tasks - create video
                        if task_type == TaskType.DOWNLOAD:
                            from backend.core.models import Video, VideoSource
                            from backend.core.repositories import VideoRepository, TagRepository
                            
                            video_repo = VideoRepository(session)
                            
                            existing_video = await video_repo.get_by_external_id(
                                VideoSource(result["platform"]),
                                result["external_id"]
                            )
                            
                            if existing_video:
                                existing_video.directory_path = result["directory_path"]
                                existing_video.title = result["metadata"].get("title", existing_video.title)
                                video = existing_video
                                worker_logger.info(f"Video already exists, updated: {video.id}")
                            else:
                                video = Video(
                                    id=result["video_id"],
                                    title=result["metadata"].get("title", "Unknown"),
                                    source=VideoSource(result["platform"]),
                                    external_id=result["external_id"],
                                    channel_name=result["metadata"].get("channel_name"),
                                    duration=result["metadata"].get("duration"),
                                    description=result["metadata"].get("description"),
                                    directory_path=result["directory_path"],
                                )
                                await video_repo.create(video)
                                worker_logger.info(f"Video created: {video.id} - {video.title}")
                            
                            tag_repo = TagRepository(session)
                            tags_to_add = []
                            
                            platform_tag_map = {"youtube": "YouTube", "bilibili": "Bilibili"}
                            platform_tag_name = platform_tag_map.get(result["platform"])
                            if platform_tag_name:
                                tags_to_add.append(platform_tag_name)
                            
                            channel_name = result["metadata"].get("channel_name")
                            if channel_name:
                                tags_to_add.append(channel_name)
                            
                            user_tags = task.payload.get("tags", []) if task.payload else []
                            tags_to_add.extend(user_tags)
                            
                            for tag_name in tags_to_add:
                                if tag_name and tag_name.strip():
                                    tag = await tag_repo.get_or_create(tag_name.strip())
                                    await session.refresh(video, ['tags'])
                                    if tag not in video.tags:
                                        video.tags.append(tag)
                            
                            task.video_id = video.id
                        
                        # Complete task
                        await queue.complete_task(task.id, result)
                        await session.commit()
                        worker_logger.info(f"Task completed: {task.id}")
                        
                        # Broadcast task completed via WebSocket
                        from backend.app.routers.websocket import broadcast_task_update
                        await broadcast_task_update(
                            task_id=task.id,
                            task_type=task_type.value,
                            status="completed",
                            video_id=task.video_id,
                            result=result,
                        )
                        
                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        worker_logger.error(f"Task failed: {task.id} - {e}\n{error_detail}")
                        await queue.fail_task(task.id, str(e))
                        await session.commit()
                        
                        from backend.app.routers.websocket import broadcast_task_update
                        await broadcast_task_update(
                            task_id=task.id,
                            task_type=task_type.value,
                            status="failed",
                            video_id=task.video_id,
                            error=str(e),
                        )
                    
                    finally:
                        # Mark this type as not running
                        async with running_tasks_lock:
                            running_tasks[task_type] = False
                            
            except Exception as e:
                worker_logger.error(f"Worker loop error for {task_type.value}: {e}")
                async with running_tasks_lock:
                    running_tasks[task_type] = False
                await asyncio.sleep(2)

    # Create parallel worker tasks for each task type
    worker_tasks = []
    for task_type in task_types:
        service = services[task_type]
        worker_task = asyncio.create_task(
            process_task_type(task_type, service),
            name=f"worker_{task_type.value}"
        )
        worker_tasks.append(worker_task)
    
    # Store worker tasks and services for cleanup and cancellation
    app.state.worker_tasks = worker_tasks
    app.state.services = services
    
    logger.info(f"Started {len(worker_tasks)} parallel workers (pipeline mode enabled)")
    logger.info("SRT Flow backend ready!")
    yield
    
    # Shutdown
    logger.info("SRT Flow backend shutting down...")
    
    # Stop all workers
    if hasattr(app.state, 'worker_tasks'):
        for worker_task in app.state.worker_tasks:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        logger.info("All workers stopped")
    
    await close_database()
    logger.info("Database connection closed")


def create_app() -> FastAPI:
    """
    Application factory function.
    
    Creates and configures the FastAPI application instance.
    """
    app = FastAPI(
        title="SRT Flow API",
        description="Video processing workflow API for subtitle translation and synthesis",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    # Include API router
    app.include_router(api_router)
    
    # Include WebSocket router
    app.include_router(ws_router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return success_response(
            data={
                "name": "SRT Flow API",
                "version": "0.1.0",
                "docs": "/docs"
            },
            message="Welcome to SRT Flow API"
        )
    
    # Mount static files for frontend (if directory exists)
    static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    from backend.core.config import get_system_settings
    
    settings = get_system_settings()
    port = int(settings.port) if hasattr(settings, 'port') else 8010
    
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
