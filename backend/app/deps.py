"""
Dependency injection utilities.

This module provides common dependencies for FastAPI endpoints.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import get_config_manager, ConfigManager, get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency.
    
    Yields a database session and ensures proper cleanup.
    """
    async for session in get_db_session():
        yield session


def get_config() -> ConfigManager:
    """
    Configuration dependency.
    
    Returns the configuration manager instance.
    """
    return get_config_manager()


async def get_queue():
    """
    Task queue dependency.
    
    Returns the queue manager instance.
    Will be implemented in TASK-021.
    """
    # TODO: Implement when queue module is ready
    return None
