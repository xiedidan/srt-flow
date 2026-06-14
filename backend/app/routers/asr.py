"""
ASR (Automatic Speech Recognition) API endpoints.

Provides REST API for ASR model management.
"""
import asyncio
import os
import threading
from pathlib import Path
from typing import Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from backend.app.schemas import success_response
from backend.core import get_system_settings
from backend.core.logger import get_logger


router = APIRouter(prefix="/asr", tags=["ASR"])
logger = get_logger("asr.api")

# Model download status tracking (thread-safe)
_download_status: Dict[str, Dict] = {}
_status_lock = threading.Lock()

# Supported platforms
SUPPORTED_PLATFORMS = ["windows", "linux"]

# Model size estimates in MB (approximate)
MODEL_SIZES_MB = {
    "tiny": 75,
    "base": 145,
    "small": 465,
    "medium": 1500,
    "large": 3000,
    "large-v2": 3000,
    "large-v3": 3000,
}

# Supported engines that need executable download
SUPPORTED_ENGINES = ["faster_whisper_xxl"]

# Engine executable download URLs by engine and platform
ENGINE_DOWNLOAD_URLS = {
    "faster_whisper_xxl": {
        "windows": "https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_windows.7z",
        "linux": "https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_linux.7z",
    },
}

# Engine executable names by engine
ENGINE_EXECUTABLE_NAMES = {
    "faster_whisper_xxl": {"windows": "faster-whisper-xxl.exe", "linux": "faster-whisper-xxl"},
}


# ============================================================================
# Schemas
# ============================================================================




# ============================================================================
# Model Path Utilities
# ============================================================================

def get_whisper_model_path(model_size: str) -> Path:
    """Get the expected model path for a Whisper model.
    
    All Whisper engines (whisper_local, faster_whisper_xxl) share the same model files.
    """
    settings = get_system_settings()
    models_dir = Path(settings.data_dir) / "models"
    return models_dir / f"faster-whisper-{model_size}"


def check_model_downloaded(model_size: str) -> bool:
    """Check if a Whisper model is downloaded."""
    model_path = get_whisper_model_path(model_size)
    
    if model_path.exists() and model_path.is_dir():
        # faster-whisper models have model.bin
        if (model_path / "model.bin").exists():
            return True
        # Or check for config.json as indicator
        if (model_path / "config.json").exists():
            return True
    
    return False


def get_model_size_on_disk(model_size: str) -> int:
    """Get the size of downloaded model in bytes."""
    model_path = get_whisper_model_path(model_size)
    
    if not model_path.exists():
        return 0
    
    total_size = 0
    for f in model_path.rglob("*"):
        if f.is_file():
            total_size += f.stat().st_size
    
    return total_size


def get_all_models_status() -> List[Dict]:
    """Get download status for all model sizes.
    
    Models are shared across all Whisper engines.
    """
    model_sizes = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    
    result = []
    for size in model_sizes:
        downloaded = check_model_downloaded(size)
        size_on_disk = get_model_size_on_disk(size) if downloaded else 0
        
        # Check download status (use model_size as key since models are shared)
        key = size
        with _status_lock:
            dl_status = _download_status.get(key, {})
        
        result.append({
            "model_size": size,
            "downloaded": downloaded,
            "size_mb": size_on_disk / (1024 * 1024) if size_on_disk else 0,
            "total_size_mb": MODEL_SIZES_MB.get(size, 0),
            "download_status": dl_status.get("status", "idle"),
            "download_progress": dl_status.get("progress", 0),
            "downloaded_mb": dl_status.get("downloaded_mb", 0),
            "total_mb": dl_status.get("total_mb", MODEL_SIZES_MB.get(size, 0)),
        })
    
    return result


# ============================================================================
# Background Download Task
# ============================================================================

def update_download_progress(key: str, model_path: Path, total_mb: float):
    """Update download progress by checking file sizes on disk."""
    if not model_path.exists():
        return
    
    total_size = 0
    for f in model_path.rglob("*"):
        if f.is_file():
            try:
                total_size += f.stat().st_size
            except:
                pass
    
    downloaded_mb = total_size / (1024 * 1024)
    progress = min(int((downloaded_mb / total_mb) * 100), 99) if total_mb > 0 else 0
    
    with _status_lock:
        if key in _download_status and _download_status[key].get("status") == "downloading":
            _download_status[key].update({
                "progress": progress,
                "downloaded_mb": round(downloaded_mb, 1),
            })


def download_model_sync(model_size: str):
    """Synchronous model download (runs in thread).
    
    Models are shared across all Whisper engines.
    """
    key = model_size
    total_mb = MODEL_SIZES_MB.get(model_size, 1000)
    
    settings = get_system_settings()
    models_dir = Path(settings.data_dir) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    local_dir = models_dir / f"faster-whisper-{model_size}"
    
    with _status_lock:
        _download_status[key] = {
            "model_size": model_size,
            "status": "downloading",
            "progress": 0,
            "downloaded_mb": 0,
            "total_mb": total_mb,
            "error": ""
        }
    
    # Start progress monitoring thread
    stop_monitoring = threading.Event()
    
    def monitor_progress():
        """Monitor download progress by checking file sizes."""
        while not stop_monitoring.is_set():
            update_download_progress(key, local_dir, total_mb)
            stop_monitoring.wait(1.0)  # Check every second
    
    monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
    monitor_thread.start()
    
    try:
        logger.info(f"Starting download: model {model_size}")
        
        # Get global proxy config
        from backend.core.config import get_config_manager
        import os
        
        config_manager = get_config_manager()
        # Use sync method to get cached config (global config is loaded at startup)
        proxy_url = None
        try:
            # Try to get proxy from global config cache
            if "global" in config_manager._cache:
                proxy_url = config_manager._cache["global"].proxy_url
        except Exception:
            pass
        
        # Set proxy environment variables for huggingface_hub
        old_http_proxy = os.environ.get("HTTP_PROXY")
        old_https_proxy = os.environ.get("HTTPS_PROXY")
        
        if proxy_url:
            logger.info(f"Using proxy: {proxy_url}")
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
        
        try:
            # Use huggingface_hub to download
            from huggingface_hub import snapshot_download
            
            repo_id = f"Systran/faster-whisper-{model_size}"
            
            # Download the model
            snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_dir),
                local_dir_use_symlinks=False,
            )
        finally:
            # Restore original proxy settings
            if old_http_proxy is not None:
                os.environ["HTTP_PROXY"] = old_http_proxy
            elif "HTTP_PROXY" in os.environ:
                del os.environ["HTTP_PROXY"]
            if old_https_proxy is not None:
                os.environ["HTTPS_PROXY"] = old_https_proxy
            elif "HTTPS_PROXY" in os.environ:
                del os.environ["HTTPS_PROXY"]
        
        # Stop monitoring
        stop_monitoring.set()
        monitor_thread.join(timeout=2)
        
        # Verify download
        if check_model_downloaded(model_size):
            actual_size = get_model_size_on_disk(model_size)
            with _status_lock:
                _download_status[key].update({
                    "status": "completed",
                    "progress": 100,
                    "downloaded_mb": round(actual_size / (1024 * 1024), 1),
                    "total_mb": round(actual_size / (1024 * 1024), 1),
                })
            logger.info(f"Download completed: model {model_size}")
        else:
            raise Exception("Model files not found after download")
        
    except Exception as e:
        logger.error(f"Download failed: model {model_size} - {e}")
        stop_monitoring.set()
        with _status_lock:
            _download_status[key].update({
                "status": "failed",
                "error": str(e)
            })


async def download_model_task(model_size: str):
    """Background task to download a Whisper model."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_model_sync, model_size)


# ============================================================================
# Engine Executable Utilities
# ============================================================================

def get_engine_path(engine: str, platform: str) -> Path:
    """Get the expected path for engine executable."""
    settings = get_system_settings()
    models_dir = Path(settings.data_dir) / "models"
    return models_dir / f"{engine}-{platform}"


def check_engine_downloaded(engine: str, platform: str) -> bool:
    """Check if engine executable is downloaded for the platform."""
    engine_path = get_engine_path(engine, platform)
    if not engine_path.exists():
        return False
    
    # Check for executable
    exe_name = ENGINE_EXECUTABLE_NAMES.get(engine, {}).get(platform)
    if not exe_name:
        return False
    
    # Check in root
    if (engine_path / exe_name).exists():
        return True
    
    # Some archives extract to a subdirectory - search recursively
    for root, dirs, files in engine_path.walk() if hasattr(engine_path, 'walk') else os.walk(engine_path):
        root_path = Path(root) if not isinstance(root, Path) else root
        if exe_name in files:
            return True
    
    return False


def get_engine_size_on_disk(engine: str, platform: str) -> int:
    """Get the size of downloaded engine in bytes."""
    engine_path = get_engine_path(engine, platform)
    if not engine_path.exists():
        return 0
    
    total_size = 0
    for f in engine_path.rglob("*"):
        if f.is_file():
            total_size += f.stat().st_size
    return total_size


def get_all_engine_status(engine: str) -> List[Dict]:
    """Get download status for all platforms for a specific engine."""
    result = []
    for platform in SUPPORTED_PLATFORMS:
        downloaded = check_engine_downloaded(engine, platform)
        size_on_disk = get_engine_size_on_disk(engine, platform) if downloaded else 0
        
        key = f"{engine}_{platform}"
        with _status_lock:
            dl_status = _download_status.get(key, {})
        
        result.append({
            "engine": engine,
            "platform": platform,
            "downloaded": downloaded,
            "size_mb": size_on_disk / (1024 * 1024) if size_on_disk else 0,
            "download_status": dl_status.get("status", "idle"),
            "download_progress": dl_status.get("progress", 0),
            "downloaded_mb": dl_status.get("downloaded_mb", 0),
            "total_mb": dl_status.get("total_mb", 0),
            "download_error": dl_status.get("error", ""),
        })
    return result


def download_engine_sync(engine: str, platform: str):
    """Synchronous engine download (runs in thread)."""
    import os
    import zipfile
    import tarfile
    import tempfile
    
    key = f"{engine}_{platform}"
    url = ENGINE_DOWNLOAD_URLS.get(engine, {}).get(platform)
    
    if not url:
        with _status_lock:
            _download_status[key] = {
                "engine": engine,
                "platform": platform,
                "status": "failed",
                "error": f"No download URL for engine {engine} platform {platform}"
            }
        return
    
    settings = get_system_settings()
    models_dir = Path(settings.data_dir) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    engine_dir = models_dir / f"{engine}-{platform}"
    
    with _status_lock:
        _download_status[key] = {
            "engine": engine,
            "platform": platform,
            "status": "downloading",
            "progress": 0,
            "downloaded_mb": 0,
            "total_mb": 0,
            "error": ""
        }
    
    try:
        logger.info(f"Starting engine download: {engine} for {platform}")
        
        # Get proxy config
        from backend.core.config import get_config_manager
        import httpx
        import os
        
        config_manager = get_config_manager()
        proxy_url = None
        try:
            if "global" in config_manager._cache:
                proxy_url = config_manager._cache["global"].proxy_url
        except Exception:
            pass
        
        # Set proxy via environment variables (most compatible way)
        old_http_proxy = os.environ.get("HTTP_PROXY")
        old_https_proxy = os.environ.get("HTTPS_PROXY")
        
        if proxy_url:
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
        
        # Download file with progress
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            with httpx.Client(timeout=600.0, follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("content-length", 0))
                    total_mb = total_size / (1024 * 1024)
                    
                    with _status_lock:
                        _download_status[key]["total_mb"] = round(total_mb, 1)
                    
                    downloaded = 0
                    with open(tmp_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            downloaded_mb = downloaded / (1024 * 1024)
                            progress = int((downloaded / total_size) * 80) if total_size > 0 else 0
                            
                            with _status_lock:
                                _download_status[key].update({
                                    "progress": progress,
                                    "downloaded_mb": round(downloaded_mb, 1),
                                })
            
            # Extract archive - run in thread pool to avoid blocking
            logger.info(f"Extracting engine archive: {engine} for {platform}")
            with _status_lock:
                _download_status[key]["progress"] = 85
            
            # Remove existing directory
            if engine_dir.exists():
                import shutil
                shutil.rmtree(engine_dir)
            engine_dir.mkdir(parents=True, exist_ok=True)
            
            def extract_archive():
                """Extract archive in separate thread to avoid blocking."""
                if url.endswith(".zip"):
                    with zipfile.ZipFile(tmp_path, "r") as zf:
                        zf.extractall(engine_dir)
                elif url.endswith(".7z"):
                    # Use system 7z command for better compatibility
                    import subprocess
                    import shutil
                    import platform
                    
                    # Try to find 7z executable
                    seven_zip_cmd = None
                    
                    # First try PATH
                    for cmd in ["7z", "7za", "7zz"]:
                        if shutil.which(cmd):
                            seven_zip_cmd = cmd
                            break
                    
                    # If not in PATH, try common Windows installation paths
                    if not seven_zip_cmd and platform.system() == "Windows":
                        common_paths = [
                            r"C:\Program Files\7-Zip\7z.exe",
                            r"C:\Program Files (x86)\7-Zip\7z.exe",
                        ]
                        for path in common_paths:
                            if os.path.exists(path):
                                seven_zip_cmd = path
                                break
                    
                    if not seven_zip_cmd:
                        # Fallback to py7zr (may not support all compression methods)
                        try:
                            import py7zr
                            with py7zr.SevenZipFile(tmp_path, "r") as archive:
                                archive.extractall(path=engine_dir)
                        except Exception as e:
                            raise Exception(
                                f"Failed to extract 7z archive. Please install 7-Zip: "
                                f"https://www.7-zip.org/download.html. Error: {e}"
                            )
                    else:
                        # Use system 7z command
                        result = subprocess.run(
                            [seven_zip_cmd, "x", tmp_path, f"-o{engine_dir}", "-y"],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode != 0:
                            raise Exception(f"7z extraction failed: {result.stderr}")
                else:  # tar.gz
                    with tarfile.open(tmp_path, "r:gz") as tf:
                        tf.extractall(engine_dir)
            
            # Run extraction in thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(extract_archive)
                future.result()  # Wait for completion but don't block event loop
            
            with _status_lock:
                _download_status[key]["progress"] = 95
            
            # Verify download
            if check_engine_downloaded(engine, platform):
                actual_size = get_engine_size_on_disk(engine, platform)
                with _status_lock:
                    _download_status[key].update({
                        "status": "completed",
                        "progress": 100,
                        "downloaded_mb": round(actual_size / (1024 * 1024), 1),
                        "total_mb": round(actual_size / (1024 * 1024), 1),
                    })
                logger.info(f"Engine download completed: {engine} for {platform}")
            else:
                raise Exception("Executable not found after extraction")
                
        finally:
            # Clean up temp file with retry (Windows file locking issue)
            if os.path.exists(tmp_path):
                import time
                max_retries = 10
                retry_delay = 2.0  # 2 seconds per retry, total 20 seconds
                for attempt in range(max_retries):
                    try:
                        os.unlink(tmp_path)
                        break
                    except PermissionError:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)  # Wait for file handles to be released
                        else:
                            logger.warning(f"Failed to delete temp file after {max_retries * retry_delay}s: {tmp_path}")
            
            # Restore original proxy settings
            if old_http_proxy is not None:
                os.environ["HTTP_PROXY"] = old_http_proxy
            elif "HTTP_PROXY" in os.environ:
                del os.environ["HTTP_PROXY"]
            if old_https_proxy is not None:
                os.environ["HTTPS_PROXY"] = old_https_proxy
            elif "HTTPS_PROXY" in os.environ:
                del os.environ["HTTPS_PROXY"]
                
    except Exception as e:
        logger.error(f"Engine download failed: {engine} for {platform} - {e}")
        with _status_lock:
            _download_status[key].update({
                "status": "failed",
                "error": str(e)
            })


async def download_engine_task(engine: str, platform: str):
    """Background task to download engine executable."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_engine_sync, engine, platform)


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/models")
async def list_models():
    """List all available Whisper models and their download status.
    
    Models are shared across all Whisper engines (whisper_local, faster_whisper_xxl).
    """
    models = get_all_models_status()
    return success_response(data={"models": models})


@router.get("/models/{model_size}")
async def get_model_status(model_size: str):
    """Get download status for a specific model.
    
    Models are shared across all Whisper engines.
    """
    valid_sizes = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    if model_size not in valid_sizes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model size. Must be one of: {valid_sizes}"
        )
    
    downloaded = check_model_downloaded(model_size)
    size_on_disk = get_model_size_on_disk(model_size) if downloaded else 0
    
    key = model_size
    with _status_lock:
        download_info = _download_status.get(key, {})
    
    return success_response(data={
        "model_size": model_size,
        "downloaded": downloaded,
        "size_mb": round(size_on_disk / (1024 * 1024), 1) if size_on_disk else 0,
        "total_size_mb": MODEL_SIZES_MB.get(model_size, 0),
        "download_status": download_info.get("status", "idle"),
        "download_progress": download_info.get("progress", 0),
        "downloaded_mb": download_info.get("downloaded_mb", 0),
        "total_mb": download_info.get("total_mb", MODEL_SIZES_MB.get(model_size, 0)),
        "download_error": download_info.get("error", ""),
    })


class ModelDownloadRequestSimple(BaseModel):
    """Request body for model download."""
    model_size: str = Field(..., description="Model size to download")


@router.post("/models/download")
async def download_model(request: ModelDownloadRequestSimple, background_tasks: BackgroundTasks):
    """Start downloading a Whisper model.
    
    Models are cross-platform and shared by all Whisper engines.
    For engine executables, use /engines/download endpoint.
    """
    valid_sizes = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    if request.model_size not in valid_sizes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model size. Must be one of: {valid_sizes}"
        )
    
    key = request.model_size
    
    with _status_lock:
        current_status = _download_status.get(key, {}).get("status")
    
    if current_status == "downloading":
        return success_response(
            data={"status": "already_downloading"},
            message="正在下载中"
        )
    
    already_downloaded = check_model_downloaded(request.model_size)
    background_tasks.add_task(download_model_task, request.model_size)
    
    return success_response(
        data={
            "model_size": request.model_size,
            "status": "started",
            "already_downloaded": already_downloaded,
            "total_mb": MODEL_SIZES_MB.get(request.model_size, 0),
        },
        message="模型下载已开始" if not already_downloaded else "模型已存在，正在重新下载"
    )


@router.delete("/models/{model_size}")
async def delete_model(model_size: str):
    """Delete a downloaded Whisper model.
    
    Models are shared across all Whisper engines.
    """
    import shutil
    
    valid_sizes = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    if model_size not in valid_sizes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model size. Must be one of: {valid_sizes}"
        )
    
    # Check if model is currently downloading
    key = model_size
    with _status_lock:
        current_status = _download_status.get(key, {}).get("status")
    
    if current_status == "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法删除正在下载的模型"
        )
    
    # Check if model exists
    if not check_model_downloaded(model_size):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型未下载"
        )
    
    model_path = get_whisper_model_path(model_size)
    size_mb = get_model_size_on_disk(model_size) / (1024 * 1024)
    
    try:
        shutil.rmtree(model_path)
        logger.info(f"Deleted model: {model_size} ({size_mb:.1f} MB)")
        
        # Clear download status if exists
        with _status_lock:
            if key in _download_status:
                del _download_status[key]
        
        return success_response(
            data={
                "model_size": model_size,
                "deleted_size_mb": round(size_mb, 1)
            },
            message=f"模型 {model_size} 已删除"
        )
    except Exception as e:
        logger.error(f"Failed to delete model {model_size}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除模型失败: {str(e)}"
        )


# ============================================================================
# Engine Executable Endpoints
# ============================================================================

@router.get("/engines")
async def list_engines():
    """List all supported engines."""
    return success_response(data={
        "engines": SUPPORTED_ENGINES,
        "platforms": SUPPORTED_PLATFORMS
    })


@router.get("/engines/{engine}")
async def list_engine_status(engine: str):
    """List engine download status for all platforms."""
    if engine not in SUPPORTED_ENGINES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid engine. Must be one of: {SUPPORTED_ENGINES}"
        )
    
    engine_list = get_all_engine_status(engine)
    return success_response(data={"engine": engine, "platforms": engine_list})


@router.get("/engines/{engine}/{platform}")
async def get_engine_status(engine: str, platform: str):
    """Get engine download status for a specific platform."""
    if engine not in SUPPORTED_ENGINES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid engine. Must be one of: {SUPPORTED_ENGINES}"
        )
    
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform. Must be one of: {SUPPORTED_PLATFORMS}"
        )
    
    downloaded = check_engine_downloaded(engine, platform)
    size_on_disk = get_engine_size_on_disk(engine, platform) if downloaded else 0
    
    key = f"{engine}_{platform}"
    with _status_lock:
        download_info = _download_status.get(key, {})
    
    return success_response(data={
        "engine": engine,
        "platform": platform,
        "downloaded": downloaded,
        "size_mb": round(size_on_disk / (1024 * 1024), 1) if size_on_disk else 0,
        "download_status": download_info.get("status", "idle"),
        "download_progress": download_info.get("progress", 0),
        "downloaded_mb": download_info.get("downloaded_mb", 0),
        "total_mb": download_info.get("total_mb", 0),
        "download_error": download_info.get("error", ""),
    })


class EngineDownloadRequest(BaseModel):
    """Request body for engine download."""
    engine: str = Field(..., description="Engine type: whisper_local or faster_whisper_xxl")
    platform: str = Field(..., description="Target platform: windows, linux, macos")


@router.post("/engines/download")
async def download_engine(request: EngineDownloadRequest, background_tasks: BackgroundTasks):
    """Start downloading an engine executable."""
    if request.engine not in SUPPORTED_ENGINES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid engine. Must be one of: {SUPPORTED_ENGINES}"
        )
    
    if request.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform. Must be one of: {SUPPORTED_PLATFORMS}"
        )
    
    key = f"{request.engine}_{request.platform}"
    
    with _status_lock:
        current_status = _download_status.get(key, {}).get("status")
    
    if current_status == "downloading":
        return success_response(
            data={"status": "already_downloading"},
            message="正在下载中"
        )
    
    already_downloaded = check_engine_downloaded(request.engine, request.platform)
    background_tasks.add_task(download_engine_task, request.engine, request.platform)
    
    return success_response(
        data={
            "engine": request.engine,
            "platform": request.platform,
            "status": "started",
            "already_downloaded": already_downloaded,
        },
        message="引擎下载已开始" if not already_downloaded else "已存在，正在重新下载"
    )


@router.delete("/engines/{engine}/{platform}")
async def delete_engine(engine: str, platform: str):
    """Delete downloaded engine for a specific platform."""
    import shutil
    
    if engine not in SUPPORTED_ENGINES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid engine. Must be one of: {SUPPORTED_ENGINES}"
        )
    
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform. Must be one of: {SUPPORTED_PLATFORMS}"
        )
    
    key = f"{engine}_{platform}"
    with _status_lock:
        current_status = _download_status.get(key, {}).get("status")
    
    if current_status == "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法删除正在下载的文件"
        )
    
    if not check_engine_downloaded(engine, platform):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该平台的引擎未下载"
        )
    
    engine_path = get_engine_path(engine, platform)
    size_mb = get_engine_size_on_disk(engine, platform) / (1024 * 1024)
    
    try:
        shutil.rmtree(engine_path)
        logger.info(f"Deleted engine {engine} for {platform} ({size_mb:.1f} MB)")
        
        with _status_lock:
            if key in _download_status:
                del _download_status[key]
        
        return success_response(
            data={
                "engine": engine,
                "platform": platform,
                "deleted_size_mb": round(size_mb, 1)
            },
            message=f"引擎 ({platform}) 已删除"
        )
    except Exception as e:
        logger.error(f"Failed to delete engine {engine} for {platform}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )
