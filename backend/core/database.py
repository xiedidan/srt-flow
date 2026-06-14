"""
Database Manager Module.

Provides SQLite database connection management, session handling,
and initialization for SRT Flow.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from backend.core.models import Base
from backend.core.exceptions import (
    DatabaseNotInitializedError,
    DatabaseConnectionError,
)


class DatabaseManager:
    """
    Manages SQLite database connections and sessions.
    
    Provides async database operations using SQLAlchemy 2.0 async API.
    Uses singleton pattern to ensure single database connection.
    """
    
    _instance: Optional["DatabaseManager"] = None
    _lock = asyncio.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, database_path: str = "data/srtflow.db"):
        """
        Initialize database manager.
        
        Args:
            database_path: Path to SQLite database file
        """
        if self._initialized:
            return
        
        self._database_path = database_path
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized."""
        return self._initialized and self._engine is not None
    
    @property
    def engine(self) -> AsyncEngine:
        """Get database engine."""
        if not self._engine:
            raise DatabaseNotInitializedError()
        return self._engine
    
    async def initialize(self) -> None:
        """
        Initialize database connection and create tables.
        
        Creates the database file if it doesn't exist,
        sets up WAL mode, and creates all tables.
        """
        async with self._lock:
            if self._initialized:
                return
            
            try:
                # Ensure directory exists
                db_path = Path(self._database_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create async engine
                # Use StaticPool for SQLite async compatibility
                self._engine = create_async_engine(
                    f"sqlite+aiosqlite:///{self._database_path}",
                    echo=False,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False},
                )
                
                # Configure SQLite for better performance
                @event.listens_for(self._engine.sync_engine, "connect")
                def set_sqlite_pragma(dbapi_conn, connection_record):
                    cursor = dbapi_conn.cursor()
                    # Enable WAL mode for better concurrency
                    cursor.execute("PRAGMA journal_mode=WAL")
                    # Enable foreign keys
                    cursor.execute("PRAGMA foreign_keys=ON")
                    # Optimize for performance
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
                    cursor.close()
                
                # Create session factory
                self._session_factory = async_sessionmaker(
                    bind=self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                )
                
                # Create all tables
                async with self._engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                
                self._initialized = True
                
            except Exception as e:
                self._engine = None
                self._session_factory = None
                raise DatabaseConnectionError(f"Failed to initialize database: {e}")
    
    async def close(self) -> None:
        """Close database connection and cleanup resources."""
        async with self._lock:
            if self._engine:
                await self._engine.dispose()
                self._engine = None
                self._session_factory = None
                self._initialized = False
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session with automatic transaction management.
        
        Usage:
            async with db.session() as session:
                # perform database operations
                # auto-commits on success, rollbacks on exception
        
        Yields:
            AsyncSession: Database session
        """
        if not self._session_factory:
            raise DatabaseNotInitializedError()
        
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def get_session(self) -> AsyncSession:
        """
        Get a new database session (caller manages lifecycle).
        
        For use with FastAPI dependency injection.
        Caller is responsible for commit/rollback/close.
        
        Returns:
            AsyncSession: Database session
        """
        if not self._session_factory:
            raise DatabaseNotInitializedError()
        return self._session_factory()
    
    async def execute_raw(self, sql: str) -> None:
        """
        Execute raw SQL statement.
        
        Args:
            sql: SQL statement to execute
        """
        async with self.session() as session:
            await session.execute(text(sql))
    
    async def health_check(self) -> bool:
        """
        Check database connectivity.
        
        Returns:
            bool: True if database is accessible
        """
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# ============================================================================
# Global Instance and Helpers
# ============================================================================

_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        from backend.core import get_system_settings
        settings = get_system_settings()
        _db_manager = DatabaseManager(settings.database_path)
    return _db_manager


async def init_database(database_path: Optional[str] = None) -> DatabaseManager:
    """
    Initialize the global database manager.
    
    Args:
        database_path: Optional custom database path
        
    Returns:
        DatabaseManager: Initialized database manager
    """
    global _db_manager
    
    if database_path:
        _db_manager = DatabaseManager(database_path)
    else:
        _db_manager = get_database_manager()
    
    await _db_manager.initialize()
    return _db_manager


async def close_database() -> None:
    """Close the global database connection."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session.
    
    Usage in routes:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    db = get_database_manager()
    if not db.is_initialized:
        await db.initialize()
    
    session = await db.get_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
