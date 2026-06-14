"""
Core module exceptions.

Custom exceptions for configuration and other core modules.
"""


class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigNotFoundError(ConfigError):
    """Raised when a configuration key is not found."""
    def __init__(self, category: str, key: str):
        self.category = category
        self.key = key
        super().__init__(f"Configuration not found: {category}.{key}")


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message)


class ConfigEncryptionError(ConfigError):
    """Raised when encryption operation fails."""
    pass


class ConfigDecryptionError(ConfigError):
    """Raised when decryption operation fails."""
    pass


# ============================================================================
# Database Exceptions
# ============================================================================


class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


class DatabaseNotInitializedError(DatabaseError):
    """Raised when database is not initialized."""
    def __init__(self, message: str = "Database not initialized"):
        super().__init__(message)


class EntityNotFoundError(DatabaseError):
    """Raised when an entity is not found."""
    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} not found: {entity_id}")


class DuplicateEntityError(DatabaseError):
    """Raised when entity already exists (unique constraint violation)."""
    def __init__(self, entity_type: str, message: str = None):
        self.entity_type = entity_type
        super().__init__(message or f"Duplicate {entity_type}")


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass
