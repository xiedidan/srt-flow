"""
AI Provider management API routes.

Provides CRUD operations for AI provider configurations.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.deps import get_db_session
from backend.core.models import AIProvider, AIProviderType
from backend.core.repositories import AIProviderRepository
from backend.core.encryption import (
    get_encryption_manager, 
    get_rsa_encryption_manager,
    EncryptionManager,
    RSAEncryptionManager,
)
from backend.core.config import get_system_settings
from backend.core.logger import get_logger


router = APIRouter(prefix="/ai-providers", tags=["ai-providers"])
logger = get_logger("api.ai_providers")


# Default base URLs for each API type
DEFAULT_BASE_URLS = {
    AIProviderType.DEEPSEEK: "https://api.deepseek.com/v1",
    AIProviderType.OPENAI: "https://api.openai.com/v1",
    AIProviderType.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
    AIProviderType.OPENAI_COMPATIBLE: None,  # Must be provided
}


# ============================================================================
# Request/Response Models
# ============================================================================

class AIProviderCreate(BaseModel):
    """Request model for creating AI provider."""
    name: str = Field(..., min_length=1, max_length=100)
    api_type: AIProviderType
    base_url: Optional[str] = None
    api_key_encrypted: str = Field(..., min_length=1, description="RSA encrypted API key (base64)")


class AIProviderUpdate(BaseModel):
    """Request model for updating AI provider."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_type: Optional[AIProviderType] = None
    base_url: Optional[str] = None
    api_key_encrypted: Optional[str] = Field(None, description="RSA encrypted API key (base64)")
    is_enabled: Optional[bool] = None


class AIProviderResponse(BaseModel):
    """Response model for AI provider."""
    id: str
    name: str
    api_type: str
    base_url: str
    api_key_masked: str
    api_key_configured: bool
    is_enabled: bool
    created_at: str
    updated_at: str


class AIProviderTestResult(BaseModel):
    """Response model for API test result."""
    success: bool
    message: str
    latency_ms: Optional[int] = None


# ============================================================================
# Helper Functions
# ============================================================================

def get_encryption() -> EncryptionManager:
    """Get encryption manager instance."""
    settings = get_system_settings()
    return get_encryption_manager(settings.data_dir)


def get_rsa_encryption() -> RSAEncryptionManager:
    """Get RSA encryption manager instance."""
    settings = get_system_settings()
    return get_rsa_encryption_manager(settings.data_dir)


def provider_to_response(provider: AIProvider, encryption: EncryptionManager) -> AIProviderResponse:
    """Convert AIProvider model to response."""
    # Decrypt API key for masking
    try:
        decrypted_key = encryption.decrypt(provider.api_key)
        masked_key = EncryptionManager.mask_sensitive(decrypted_key)
        key_configured = True
    except Exception:
        masked_key = ""
        key_configured = False
    
    # Get effective base URL
    base_url = provider.base_url or DEFAULT_BASE_URLS.get(provider.api_type, "")
    
    return AIProviderResponse(
        id=provider.id,
        name=provider.name,
        api_type=provider.api_type.value,
        base_url=base_url or "",
        api_key_masked=masked_key,
        api_key_configured=key_configured,
        is_enabled=provider.is_enabled,
        created_at=provider.created_at.isoformat(),
        updated_at=provider.updated_at.isoformat(),
    )


# ============================================================================
# API Endpoints
# ============================================================================

# Static routes must be defined BEFORE dynamic routes to avoid path conflicts

@router.get("/types/options", response_model=Dict[str, Any])
async def get_provider_types() -> Dict[str, Any]:
    """Get available AI provider types with default URLs."""
    options = []
    for api_type in AIProviderType:
        options.append({
            "value": api_type.value,
            "label": api_type.value.replace("_", " ").title(),
            "default_url": DEFAULT_BASE_URLS.get(api_type, ""),
            "url_required": api_type == AIProviderType.OPENAI_COMPATIBLE,
        })
    
    return {
        "code": 0,
        "message": "success",
        "data": options,
    }


@router.get("/public-key", response_model=Dict[str, Any])
async def get_public_key() -> Dict[str, Any]:
    """Get RSA public key for encrypting API keys."""
    rsa_encryption = get_rsa_encryption()
    public_key_pem = rsa_encryption.get_public_key_pem()
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "public_key": public_key_pem,
        },
    }


@router.get("", response_model=Dict[str, Any])
async def list_providers(
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Get all AI providers."""
    repo = AIProviderRepository(db)
    providers = await repo.get_all()
    encryption = get_encryption()
    
    return {
        "code": 0,
        "message": "success",
        "data": [provider_to_response(p, encryption) for p in providers],
    }


@router.post("", response_model=Dict[str, Any])
async def create_provider(
    data: AIProviderCreate,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Create a new AI provider."""
    repo = AIProviderRepository(db)
    encryption = get_encryption()
    rsa_encryption = get_rsa_encryption()
    
    # Check name uniqueness
    if await repo.name_exists(data.name):
        raise HTTPException(status_code=400, detail="Provider name already exists")
    
    # Validate base_url for openai_compatible
    if data.api_type == AIProviderType.OPENAI_COMPATIBLE and not data.base_url:
        raise HTTPException(
            status_code=400, 
            detail="base_url is required for openai_compatible type"
        )
    
    # Decrypt API key from RSA, then encrypt with AES for storage
    try:
        api_key_plaintext = rsa_encryption.decrypt(data.api_key_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt API key: {e}")
        raise HTTPException(status_code=400, detail="Invalid encrypted API key")
    
    encrypted_key = encryption.encrypt(api_key_plaintext)
    
    # Create provider
    provider = AIProvider(
        name=data.name,
        api_type=data.api_type,
        base_url=data.base_url,
        api_key=encrypted_key,
    )
    
    provider = await repo.create(provider)
    await db.commit()
    
    logger.info(f"Created AI provider: {provider.name} ({provider.api_type.value})")
    
    return {
        "code": 0,
        "message": "success",
        "data": provider_to_response(provider, encryption),
    }


@router.get("/{provider_id}", response_model=Dict[str, Any])
async def get_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Get a single AI provider."""
    repo = AIProviderRepository(db)
    provider = await repo.get_by_id(provider_id)
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    encryption = get_encryption()
    
    return {
        "code": 0,
        "message": "success",
        "data": provider_to_response(provider, encryption),
    }


@router.put("/{provider_id}", response_model=Dict[str, Any])
async def update_provider(
    provider_id: str,
    data: AIProviderUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Update an AI provider."""
    repo = AIProviderRepository(db)
    provider = await repo.get_by_id(provider_id)
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    encryption = get_encryption()
    rsa_encryption = get_rsa_encryption()
    
    # Check name uniqueness if changing
    if data.name and data.name != provider.name:
        if await repo.name_exists(data.name, exclude_id=provider_id):
            raise HTTPException(status_code=400, detail="Provider name already exists")
        provider.name = data.name
    
    # Update fields
    if data.api_type is not None:
        provider.api_type = data.api_type
    
    if data.base_url is not None:
        provider.base_url = data.base_url if data.base_url else None
    
    if data.api_key_encrypted:
        # Decrypt from RSA, then encrypt with AES for storage
        try:
            api_key_plaintext = rsa_encryption.decrypt(data.api_key_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise HTTPException(status_code=400, detail="Invalid encrypted API key")
        provider.api_key = encryption.encrypt(api_key_plaintext)
    
    if data.is_enabled is not None:
        provider.is_enabled = data.is_enabled
    
    # Validate base_url for openai_compatible
    if provider.api_type == AIProviderType.OPENAI_COMPATIBLE and not provider.base_url:
        raise HTTPException(
            status_code=400,
            detail="base_url is required for openai_compatible type"
        )
    
    await repo.update(provider)
    await db.commit()
    
    logger.info(f"Updated AI provider: {provider.name}")
    
    return {
        "code": 0,
        "message": "success",
        "data": provider_to_response(provider, encryption),
    }


@router.delete("/{provider_id}", response_model=Dict[str, Any])
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Delete an AI provider."""
    repo = AIProviderRepository(db)
    provider = await repo.get_by_id(provider_id)
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider_name = provider.name
    await repo.delete(provider)
    await db.commit()
    
    logger.info(f"Deleted AI provider: {provider_name}")
    
    return {
        "code": 0,
        "message": "success",
        "data": None,
    }


@router.post("/{provider_id}/test", response_model=Dict[str, Any])
async def test_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Test AI provider connection."""
    import time
    import httpx
    
    repo = AIProviderRepository(db)
    provider = await repo.get_by_id(provider_id)
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    encryption = get_encryption()
    
    # Decrypt API key
    try:
        api_key = encryption.decrypt(provider.api_key)
    except Exception:
        return {
            "code": 0,
            "message": "success",
            "data": AIProviderTestResult(
                success=False,
                message="Failed to decrypt API key",
            ).model_dump(),
        }
    
    # Get base URL
    base_url = provider.base_url or DEFAULT_BASE_URLS.get(provider.api_type, "")
    if not base_url:
        return {
            "code": 0,
            "message": "success",
            "data": AIProviderTestResult(
                success=False,
                message="No base URL configured",
            ).model_dump(),
        }
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider.api_type == AIProviderType.GEMINI:
                # Gemini uses different API structure
                url = f"{base_url.rstrip('/')}/models?key={api_key}"
                response = await client.get(url)
            else:
                # OpenAI-compatible APIs
                url = f"{base_url.rstrip('/')}/models"
                headers = {"Authorization": f"Bearer {api_key}"}
                response = await client.get(url, headers=headers)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            return {
                "code": 0,
                "message": "success",
                "data": AIProviderTestResult(
                    success=True,
                    message="Connection successful",
                    latency_ms=latency_ms,
                ).model_dump(),
            }
        else:
            error_detail = response.text[:200] if response.text else "Unknown error"
            return {
                "code": 0,
                "message": "success",
                "data": AIProviderTestResult(
                    success=False,
                    message=f"API returned {response.status_code}: {error_detail}",
                    latency_ms=latency_ms,
                ).model_dump(),
            }
    
    except httpx.TimeoutException:
        return {
            "code": 0,
            "message": "success",
            "data": AIProviderTestResult(
                success=False,
                message="Connection timeout",
            ).model_dump(),
        }
    except Exception as e:
        return {
            "code": 0,
            "message": "success",
            "data": AIProviderTestResult(
                success=False,
                message=f"Connection failed: {str(e)}",
            ).model_dump(),
        }
