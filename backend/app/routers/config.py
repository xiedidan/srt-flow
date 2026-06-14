"""
Configuration API endpoints.

Provides REST API for managing system and user configurations.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas import success_response
from backend.app.deps import get_db
from backend.core import (
    get_config_manager,
    get_logger,
    ConfigManager,
    CONFIG_MODELS,
    SENSITIVE_FIELDS,
    ConfigValidationError,
)


router = APIRouter(prefix="/config", tags=["Configuration"])
logger = get_logger("api.config")


# ============================================================================
# Request/Response Schemas
# ============================================================================

class ConfigUpdateRequest(BaseModel):
    """Request body for updating configuration."""
    updates: Dict[str, Any] = Field(..., description="Configuration fields to update")


class SecretUpdateRequest(BaseModel):
    """Request body for updating a secret."""
    value: str = Field(..., min_length=1, description="Secret value")


class ConfigTestRequest(BaseModel):
    """Request body for testing configuration."""
    test_type: str = Field(default="connection", description="Type of test to run")


# ============================================================================
# Dependencies
# ============================================================================

async def get_config_with_db(db: AsyncSession = Depends(get_db)) -> ConfigManager:
    """Dependency to get configuration manager with database session."""
    config = get_config_manager()
    config.set_db_session(db)
    return config


# ============================================================================
# Endpoints
# ============================================================================

@router.get("")
async def list_categories(config: ConfigManager = Depends(get_config_with_db)):
    """
    List all configuration categories.
    
    Returns available configuration categories and their descriptions.
    """
    categories = []
    for name, model in CONFIG_MODELS.items():
        categories.append({
            "name": name,
            "description": model.__doc__ or f"{name} configuration",
            "has_secrets": name in SENSITIVE_FIELDS,
        })
    
    return success_response(data={"categories": categories})


# ============================================================================
# Cookie Test Endpoint (must be before /{category} to avoid route conflict)
# ============================================================================

class CookieTestRequest(BaseModel):
    """Request body for testing cookie extraction."""
    browser: str = Field(..., description="Browser name: chrome, firefox, edge, safari, opera, brave")


@router.post("/download/test-cookies")
async def test_cookies(
    request: CookieTestRequest,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Test cookie extraction from specified browser.
    
    Returns the result of yt-dlp cookie extraction test.
    """
    import asyncio
    import subprocess
    
    browser = request.browser.lower()
    valid_browsers = ["chrome", "firefox", "edge", "safari", "opera", "brave"]
    
    if browser not in valid_browsers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid browser: {browser}. Valid options: {', '.join(valid_browsers)}"
        )
    
    logger.info(f"Testing cookie extraction from browser: {browser}")
    
    try:
        # Run yt-dlp with --cookies-from-browser to test cookie extraction
        # Use --version as a simple test that doesn't require a URL
        cmd = ["yt-dlp", "--cookies-from-browser", browser, "--version"]
        
        loop = asyncio.get_event_loop()
        
        def run_test():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace",
                )
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired:
                return -1, "", "Command timed out"
            except Exception as e:
                return -1, "", str(e)
        
        returncode, stdout, stderr = await loop.run_in_executor(None, run_test)
        
        # Check for common error patterns
        error_patterns = {
            "Could not copy": f"无法复制 {browser.title()} 的 Cookie 数据库，请确保浏览器已关闭",
            "not found": f"未找到 {browser.title()} 浏览器",
            "permission denied": f"权限不足，无法访问 {browser.title()} 的 Cookie",
            "no cookies": f"未能从 {browser.title()} 获取到 Cookie",
        }
        
        combined_output = (stdout + stderr).lower()
        
        if returncode == 0:
            # Success - yt-dlp version was printed, cookies were accessible
            version = stdout.strip() if stdout else "unknown"
            return success_response(
                data={
                    "success": True,
                    "browser": browser,
                    "message": f"成功从 {browser.title()} 获取 Cookie",
                    "yt_dlp_version": version,
                },
                message="Cookie 测试成功"
            )
        else:
            # Check for specific error patterns
            error_msg = f"从 {browser.title()} 获取 Cookie 失败"
            for pattern, msg in error_patterns.items():
                if pattern in combined_output:
                    error_msg = msg
                    break
            
            # Include raw error for debugging
            raw_error = stderr.strip() if stderr else stdout.strip()
            
            return success_response(
                data={
                    "success": False,
                    "browser": browser,
                    "message": error_msg,
                    "error_detail": raw_error[:500] if raw_error else None,
                },
                message="Cookie 测试失败"
            )
            
    except Exception as e:
        logger.error(f"Cookie test failed: {e}")
        return success_response(
            data={
                "success": False,
                "browser": browser,
                "message": f"测试过程出错: {str(e)}",
            },
            message="Cookie 测试失败"
        )


# ============================================================================
# Category-based Endpoints
# ============================================================================

@router.get("/{category}")
async def get_config_by_category(
    category: str,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Get configuration for a specific category.
    
    Returns configuration with sensitive fields masked.
    """
    if category not in CONFIG_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration category '{category}' not found"
        )
    
    try:
        cfg = await config.get_config(category)
        # Explicitly include None values to ensure all fields are returned
        data = cfg.model_dump(exclude_none=False)
        
        # Log download config for debugging
        if category == "download":
            cookies_browser = getattr(cfg, 'cookies_browser', None)
            logger.info(f"[GET /config/download] cookies_browser={cookies_browser} (type={type(cookies_browser).__name__})")
        
        # Add masked secrets
        if category in SENSITIVE_FIELDS:
            for key_name in SENSITIVE_FIELDS[category]:
                masked = await config.get_masked_api_key(category, key_name)
                data[f"{key_name}_masked"] = masked
                data[f"{key_name}_configured"] = bool(masked)
        
        return success_response(data=data)
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{category}")
async def update_config_by_category(
    category: str,
    request: ConfigUpdateRequest,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Update configuration for a specific category.
    
    Accepts partial updates - only provided fields will be changed.
    """
    if category not in CONFIG_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration category '{category}' not found"
        )
    
    # Filter out secret fields from regular updates
    updates = request.updates.copy()
    if category in SENSITIVE_FIELDS:
        for key_name in SENSITIVE_FIELDS[category]:
            updates.pop(key_name, None)
    
    # Log updates for debugging
    logger.info(f"[PUT /config/{category}] Updating with: {updates}")
    
    try:
        updated = await config.update_config(category, updates)
        # Explicitly include None values to ensure all fields are returned
        data = updated.model_dump(exclude_none=False)
        
        # Add masked secrets
        if category in SENSITIVE_FIELDS:
            for key_name in SENSITIVE_FIELDS[category]:
                masked = await config.get_masked_api_key(category, key_name)
                data[f"{key_name}_masked"] = masked
                data[f"{key_name}_configured"] = bool(masked)
        
        return success_response(data=data, message="Configuration updated")
    except ConfigValidationError as e:
        logger.error(f"[PUT /config/{category}] Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.put("/{category}/secrets/{key_name}")
async def update_secret(
    category: str,
    key_name: str,
    request: SecretUpdateRequest,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Update a sensitive configuration value (e.g., API key).
    
    The value will be encrypted before storage.
    """
    if category not in SENSITIVE_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category}' has no sensitive fields"
        )
    
    if key_name not in SENSITIVE_FIELDS[category]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown sensitive field: {key_name}"
        )
    
    try:
        await config.set_api_key(category, key_name, request.value)
        masked = await config.get_masked_api_key(category, key_name)
        
        return success_response(
            data={
                "key_name": key_name,
                "masked": masked,
                "configured": True
            },
            message="Secret updated successfully"
        )
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{category}/secrets/{key_name}")
async def delete_secret(
    category: str,
    key_name: str,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Delete a sensitive configuration value.
    """
    if category not in SENSITIVE_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category}' has no sensitive fields"
        )
    
    if key_name not in SENSITIVE_FIELDS[category]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown sensitive field: {key_name}"
        )
    
    try:
        # Set to empty string effectively deletes
        await config.set_api_key(category, key_name, "")
        
        return success_response(
            data={"key_name": key_name, "configured": False},
            message="Secret deleted"
        )
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{category}/validate")
async def validate_config(
    category: str,
    request: ConfigUpdateRequest,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Validate configuration without saving.
    
    Returns validation result and any errors.
    """
    if category not in CONFIG_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration category '{category}' not found"
        )
    
    model_class = CONFIG_MODELS[category]
    
    try:
        # Try to create model with provided data
        validated = model_class(**request.updates)
        return success_response(
            data={
                "valid": True,
                "config": validated.model_dump(exclude_none=False)
            },
            message="Configuration is valid"
        )
    except Exception as e:
        return success_response(
            data={
                "valid": False,
                "errors": str(e)
            },
            message="Validation failed"
        )


@router.post("/{category}/reset")
async def reset_config(
    category: str,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Reset configuration to default values.
    
    Note: This does not reset secrets.
    """
    if category not in CONFIG_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration category '{category}' not found"
        )
    
    try:
        default = await config.reset_config(category)
        return success_response(
            data=default.model_dump(exclude_none=False),
            message="Configuration reset to defaults"
        )
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/export/all")
async def export_all_config(
    include_secrets: bool = False,
    config: ConfigManager = Depends(get_config_with_db)
):
    """
    Export all configurations.
    
    Args:
        include_secrets: Include masked secret indicators
    """
    data = await config.export_config(include_secrets=include_secrets)
    return success_response(data=data)
