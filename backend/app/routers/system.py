"""
System information API routes.

Provides system-related information like available fonts, GPU status, etc.
"""
import asyncio
import hashlib
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.schemas import success_response
from backend.core.logger import get_logger


router = APIRouter(prefix="/system", tags=["system"])
logger = get_logger("api.system")


# Common fonts that work well for subtitles
COMMON_FONTS = [
    # Chinese fonts
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "KaiTi",
    "FangSong",
    "NSimSun",
    "STHeiti",
    "STKaiti",
    "STSong",
    "STFangsong",
    "PingFang SC",
    "Hiragino Sans GB",
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "Noto Sans CJK SC",
    "Noto Serif CJK SC",
    "Source Han Sans SC",
    "Source Han Serif SC",
    # English fonts
    "Arial",
    "Helvetica",
    "Times New Roman",
    "Verdana",
    "Tahoma",
    "Georgia",
    "Trebuchet MS",
    "Impact",
    "Comic Sans MS",
    "Courier New",
    "Lucida Console",
    "Consolas",
    # Cross-platform
    "DejaVu Sans",
    "DejaVu Serif",
    "Liberation Sans",
    "Liberation Serif",
    "Roboto",
    "Open Sans",
    "Lato",
    "Ubuntu",
]


def get_windows_fonts() -> List[str]:
    """Get available fonts on Windows."""
    fonts = set()
    
    # Check Windows Fonts directory
    fonts_dir = Path("C:/Windows/Fonts")
    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            # Use filename without extension as font name (simplified)
            font_name = font_file.stem
            # Clean up font name
            for suffix in ["-Regular", "-Bold", "-Italic", "-Light", "-Medium", "Regular", "Bold"]:
                if font_name.endswith(suffix):
                    font_name = font_name[:-len(suffix)]
                    break
            fonts.add(font_name)
        
        for font_file in fonts_dir.glob("*.ttc"):
            font_name = font_file.stem
            fonts.add(font_name)
    
    # Add common fonts that are typically available
    for font in COMMON_FONTS:
        fonts.add(font)
    
    return sorted(fonts)


def get_linux_fonts() -> List[str]:
    """Get available fonts on Linux using fc-list."""
    fonts = set()
    
    try:
        # Use fc-list to get font families
        result = subprocess.run(
            ["fc-list", ":", "family"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    # fc-list may return comma-separated font families
                    for font in line.split(","):
                        font = font.strip()
                        if font:
                            fonts.add(font)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("fc-list not available, using common fonts only")
    
    # Add common fonts
    for font in COMMON_FONTS:
        fonts.add(font)
    
    return sorted(fonts)


def get_macos_fonts() -> List[str]:
    """Get available fonts on macOS."""
    fonts = set()
    
    # Check common macOS font directories
    font_dirs = [
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
    ]
    
    for fonts_dir in font_dirs:
        if fonts_dir.exists():
            for font_file in fonts_dir.glob("*.ttf"):
                fonts.add(font_file.stem)
            for font_file in fonts_dir.glob("*.ttc"):
                fonts.add(font_file.stem)
            for font_file in fonts_dir.glob("*.otf"):
                fonts.add(font_file.stem)
    
    # Add common fonts
    for font in COMMON_FONTS:
        fonts.add(font)
    
    return sorted(fonts)


@router.get("/fonts")
async def get_available_fonts():
    """
    Get list of available system fonts.
    
    Returns fonts suitable for subtitle rendering.
    """
    system = platform.system()
    
    if system == "Windows":
        fonts = get_windows_fonts()
    elif system == "Linux":
        fonts = get_linux_fonts()
    elif system == "Darwin":
        fonts = get_macos_fonts()
    else:
        fonts = sorted(COMMON_FONTS)
    
    # Categorize fonts
    chinese_fonts = []
    english_fonts = []
    other_fonts = []
    
    chinese_keywords = [
        "YaHei", "SimHei", "SimSun", "KaiTi", "FangSong", "Heiti", "Songti",
        "PingFang", "Hiragino", "WenQuanYi", "Noto Sans CJK", "Noto Serif CJK",
        "Source Han", "STHeiti", "STKaiti", "STSong", "STFangsong", "华文",
        "黑体", "宋体", "楷体", "仿宋", "微软雅黑"
    ]
    
    english_keywords = [
        "Arial", "Helvetica", "Times", "Verdana", "Tahoma", "Georgia",
        "Trebuchet", "Impact", "Comic", "Courier", "Lucida", "Consolas",
        "DejaVu", "Liberation", "Roboto", "Open Sans", "Lato", "Ubuntu"
    ]
    
    for font in fonts:
        is_chinese = any(kw.lower() in font.lower() for kw in chinese_keywords)
        is_english = any(kw.lower() in font.lower() for kw in english_keywords)
        
        if is_chinese:
            chinese_fonts.append(font)
        elif is_english:
            english_fonts.append(font)
        else:
            other_fonts.append(font)
    
    return success_response(data={
        "fonts": fonts,
        "categorized": {
            "chinese": chinese_fonts,
            "english": english_fonts,
            "other": other_fonts
        },
        "recommended": [
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "WenQuanYi Micro Hei",
            "Arial",
            "Helvetica"
        ]
    })


@router.get("/gpu")
async def get_gpu_info():
    """
    Get GPU information and available encoders.
    
    Checks for NVIDIA GPU and available hardware encoders.
    """
    gpu_available = False
    gpu_name = None
    nvenc_available = False
    
    # Check for NVIDIA GPU using nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_available = True
            gpu_name = result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Check if FFmpeg has NVENC support
    if gpu_available:
        try:
            result = subprocess.run(
                ["ffmpeg", "-encoders"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                nvenc_available = "h264_nvenc" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    return success_response(data={
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
        "nvenc_available": nvenc_available,
        "encoders": {
            "h264": [
                {"value": "libx264", "label": "H.264 (CPU)", "available": True},
                {"value": "h264_nvenc", "label": "H.264 NVENC (GPU)", "available": nvenc_available}
            ],
            "h265": [
                {"value": "libx265", "label": "H.265 (CPU)", "available": True},
                {"value": "hevc_nvenc", "label": "H.265 NVENC (GPU)", "available": nvenc_available}
            ]
        }
    })


# ============================================================================
# Subtitle Preview
# ============================================================================

class SubtitleStyleParams(BaseModel):
    """Subtitle style parameters for preview generation."""
    font_name: str = "Microsoft YaHei"
    font_size: int = 24
    font_bold: bool = False
    font_color: str = "#FFFFFF"
    font_alpha: float = 1.0
    outline_width: int = 2
    outline_color: str = "#000000"
    shadow_enabled: bool = False
    shadow_offset: int = 1
    margin_v: int = 30
    background_enabled: bool = False
    background_color: str = "#000000"
    background_alpha: float = 0.5
    background_padding_h: int = 10
    background_padding_v: int = 5


class SubtitlePreviewRequest(BaseModel):
    """Request body for subtitle preview generation."""
    translated_style: SubtitleStyleParams = SubtitleStyleParams()
    original_style: SubtitleStyleParams = SubtitleStyleParams(
        font_size=18,
        font_color="#FFFACD",
        margin_v=60,
    )
    translated_text: str = "这是翻译后的字幕示例"
    original_text: str = "This is the original subtitle example"
    width: int = 640
    height: int = 360


def _hex_to_ass_color(hex_color: str, alpha: float) -> str:
    """Convert hex color to ASS color format (&HAABBGGRR)."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    a = int((1 - alpha) * 255)
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


# Preview cache directory
PREVIEW_CACHE_DIR = Path(tempfile.gettempdir()) / "srtflow_preview_cache"


@router.post("/subtitle-preview")
async def generate_subtitle_preview(request: SubtitlePreviewRequest):
    """
    Generate a subtitle preview image using FFmpeg.
    
    Creates a single frame with the specified subtitle styles burned in,
    providing an accurate preview of how subtitles will look in the final video.
    Uses the same subtitles filter as actual synthesis for consistency.
    """
    # Ensure cache directory exists
    PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate cache key from request parameters
    cache_key = hashlib.md5(request.model_dump_json().encode()).hexdigest()
    output_path = PREVIEW_CACHE_DIR / f"preview_{cache_key}.png"
    
    # Return cached preview if exists
    if output_path.exists():
        return FileResponse(
            output_path,
            media_type="image/png",
            headers={"Cache-Control": "max-age=3600"}
        )
    
    # Create temporary SRT files for each subtitle
    translated_srt_path = PREVIEW_CACHE_DIR / f"preview_{cache_key}_translated.srt"
    original_srt_path = PREVIEW_CACHE_DIR / f"preview_{cache_key}_original.srt"
    
    # Write simple SRT content
    translated_srt_content = f"""1
00:00:00,000 --> 00:00:10,000
{request.translated_text}
"""
    original_srt_content = f"""1
00:00:00,000 --> 00:00:10,000
{request.original_text}
"""
    translated_srt_path.write_text(translated_srt_content, encoding="utf-8")
    original_srt_path.write_text(original_srt_content, encoding="utf-8")
    
    try:
        # Build force_style strings (same as actual synthesis)
        translated_style = _build_force_style(request.translated_style)
        original_style = _build_force_style(request.original_style)
        
        # Escape paths for FFmpeg
        translated_srt_escaped = str(translated_srt_path).replace("\\", "/").replace(":", "\\:")
        original_srt_escaped = str(original_srt_path).replace("\\", "/").replace(":", "\\:")
        
        # Build filter chain - same as actual synthesis
        filter_chain = (
            f"subtitles='{translated_srt_escaped}':force_style='{translated_style}',"
            f"subtitles='{original_srt_escaped}':force_style='{original_style}'"
        )
        
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"testsrc2=s={request.width}x{request.height}:d=1,hue=s=0.5:b=0.2,eq=brightness=-0.1:contrast=1.1",
            "-vf", filter_chain,
            "-frames:v", "1",
            "-y",
            str(output_path)
        ]
        
        logger.debug(f"FFmpeg preview command: {' '.join(cmd)}")
        
        # Run FFmpeg
        def run_ffmpeg():
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            return result
        
        result = await asyncio.to_thread(run_ffmpeg)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg preview failed: {result.stderr}")
            return success_response(
                code=500,
                message=f"Preview generation failed: {result.stderr[:200]}"
            )
        
        if not output_path.exists():
            return success_response(
                code=500,
                message="Preview image not created"
            )
        
        return FileResponse(
            output_path,
            media_type="image/png",
            headers={"Cache-Control": "max-age=3600"}
        )
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg preview timed out")
        return success_response(code=500, message="Preview generation timed out")
    except Exception as e:
        logger.error(f"Preview generation error: {e}")
        return success_response(code=500, message=str(e))
    finally:
        # Clean up temp SRT files
        translated_srt_path.unlink(missing_ok=True)
        original_srt_path.unlink(missing_ok=True)


def _build_force_style(style: SubtitleStyleParams) -> str:
    """Build force_style string for FFmpeg subtitles filter (same as actual synthesis)."""
    primary_color = _hex_to_ass_color(style.font_color, style.font_alpha)
    outline_color = _hex_to_ass_color(style.outline_color, 1.0)
    shadow_color = _hex_to_ass_color("#000000", 0.5 if style.shadow_enabled else 0)
    
    style_parts = [
        f"FontName={style.font_name}",
        f"FontSize={style.font_size}",
        f"Bold={1 if style.font_bold else 0}",
        f"PrimaryColour={primary_color}",
        f"OutlineColour={outline_color}",
        f"Outline={style.outline_width}",
        f"Shadow={style.shadow_offset if style.shadow_enabled else 0}",
        f"MarginV={style.margin_v}",
        f"MarginL=20",
        f"MarginR=20",
    ]
    
    if style.background_enabled:
        back_color = _hex_to_ass_color(style.background_color, style.background_alpha)
        style_parts.append("BorderStyle=4")
        style_parts.append(f"BackColour={back_color}")
    else:
        style_parts.append(f"BackColour={shadow_color}")
    
    style_parts.append("Alignment=2")  # Bottom center
    
    return ",".join(style_parts)


@router.delete("/subtitle-preview/cache")
async def clear_preview_cache():
    """Clear the subtitle preview cache."""
    if PREVIEW_CACHE_DIR.exists():
        import shutil
        shutil.rmtree(PREVIEW_CACHE_DIR)
        PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    return success_response(message="Preview cache cleared")
