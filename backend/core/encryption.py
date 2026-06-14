"""
Encryption utilities for sensitive configuration data.

Uses AES-256-GCM for symmetric encryption with PBKDF2 key derivation.
RSA-OAEP for asymmetric encryption (frontend -> backend API key transmission).
"""
import os
import base64
import secrets
import hashlib
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

from backend.core.exceptions import ConfigEncryptionError, ConfigDecryptionError


# Constants
NONCE_SIZE = 12  # 96 bits for GCM
KEY_SIZE = 32    # 256 bits for AES-256
SALT_SIZE = 16   # 128 bits
PBKDF2_ITERATIONS = 100000
KEY_FILE_NAME = ".encryption_key"
RSA_PRIVATE_KEY_FILE = ".rsa_private_key.pem"
RSA_PUBLIC_KEY_FILE = ".rsa_public_key.pem"
RSA_KEY_SIZE = 2048


class EncryptionManager:
    """
    Manages encryption and decryption of sensitive data.
    
    Uses AES-256-GCM for encryption with PBKDF2 key derivation.
    The encryption key is derived from either:
    1. ENCRYPTION_KEY environment variable
    2. Auto-generated key stored in .encryption_key file
    """
    
    def __init__(self, key_source: Optional[str] = None, data_dir: str = "data"):
        """
        Initialize encryption manager.
        
        Args:
            key_source: Encryption key or None to auto-detect
            data_dir: Directory for storing key file
        """
        self._data_dir = Path(data_dir)
        self._key = self._initialize_key(key_source)
    
    def _initialize_key(self, key_source: Optional[str]) -> bytes:
        """
        Initialize or load the encryption key.
        
        Priority:
        1. Provided key_source parameter
        2. ENCRYPTION_KEY environment variable
        3. Key file (.encryption_key)
        4. Generate new key and save to file
        """
        # Try provided key source
        if key_source:
            return self._derive_key(key_source)
        
        # Try environment variable
        env_key = os.environ.get("ENCRYPTION_KEY")
        if env_key:
            return self._derive_key(env_key)
        
        # Try key file
        key_file = self._data_dir / KEY_FILE_NAME
        if key_file.exists():
            try:
                with open(key_file, "r") as f:
                    stored_key = f.read().strip()
                    if stored_key:
                        return self._derive_key(stored_key)
            except Exception:
                pass
        
        # Generate new key
        new_key = self._generate_key()
        self._save_key_to_file(new_key)
        return self._derive_key(new_key)
    
    def _generate_key(self) -> str:
        """Generate a new random encryption key."""
        return secrets.token_urlsafe(32)
    
    def _save_key_to_file(self, key: str) -> None:
        """Save encryption key to file."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        key_file = self._data_dir / KEY_FILE_NAME
        with open(key_file, "w") as f:
            f.write(key)
        # Set restrictive permissions (owner read/write only)
        try:
            key_file.chmod(0o600)
        except Exception:
            pass  # Windows may not support chmod
    
    def _derive_key(self, password: str) -> bytes:
        """
        Derive a 256-bit key from password using PBKDF2.
        
        Uses a fixed salt derived from the password itself for deterministic
        key derivation (same password always produces same key).
        """
        # Use hash of password as salt for deterministic derivation
        salt = hashlib.sha256(password.encode()).digest()[:SALT_SIZE]
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string (nonce + ciphertext)
            
        Raises:
            ConfigEncryptionError: If encryption fails
        """
        if not plaintext:
            return ""
        
        try:
            aesgcm = AESGCM(self._key)
            nonce = os.urandom(NONCE_SIZE)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            # Combine nonce and ciphertext, then base64 encode
            encrypted = base64.b64encode(nonce + ciphertext).decode("utf-8")
            return encrypted
        except Exception as e:
            raise ConfigEncryptionError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted string.
        
        Args:
            encrypted: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ConfigDecryptionError: If decryption fails
        """
        if not encrypted:
            return ""
        
        try:
            data = base64.b64decode(encrypted.encode("utf-8"))
            nonce = data[:NONCE_SIZE]
            ciphertext = data[NONCE_SIZE:]
            
            aesgcm = AESGCM(self._key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception as e:
            raise ConfigDecryptionError(f"Decryption failed: {e}")
    
    @staticmethod
    def mask_sensitive(value: str, visible_start: int = 4, visible_end: int = 4) -> str:
        """
        Mask sensitive value for display.
        
        Args:
            value: Sensitive string to mask
            visible_start: Number of characters to show at start
            visible_end: Number of characters to show at end
            
        Returns:
            Masked string (e.g., "sk-a****key1")
        """
        if not value:
            return ""
        if len(value) <= visible_start + visible_end:
            return "*" * len(value)
        return value[:visible_start] + "****" + value[-visible_end:]


class RSAEncryptionManager:
    """
    Manages RSA asymmetric encryption for secure API key transmission.
    
    Frontend encrypts API keys with public key, backend decrypts with private key.
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize RSA encryption manager.
        
        Args:
            data_dir: Directory for storing key files
        """
        self._data_dir = Path(data_dir)
        self._private_key, self._public_key = self._initialize_keys()
    
    def _initialize_keys(self) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        """
        Initialize or load RSA key pair.
        
        Returns:
            Tuple of (private_key, public_key)
        """
        private_key_file = self._data_dir / RSA_PRIVATE_KEY_FILE
        public_key_file = self._data_dir / RSA_PUBLIC_KEY_FILE
        
        # Try to load existing keys
        if private_key_file.exists() and public_key_file.exists():
            try:
                with open(private_key_file, "rb") as f:
                    private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
                public_key = private_key.public_key()
                return private_key, public_key
            except Exception:
                pass
        
        # Generate new key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=RSA_KEY_SIZE,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # Save keys
        self._save_keys(private_key, public_key)
        
        return private_key, public_key
    
    def _save_keys(self, private_key: rsa.RSAPrivateKey, public_key: rsa.RSAPublicKey) -> None:
        """Save RSA key pair to files."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # Save private key
        private_key_file = self._data_dir / RSA_PRIVATE_KEY_FILE
        with open(private_key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        try:
            private_key_file.chmod(0o600)
        except Exception:
            pass
        
        # Save public key
        public_key_file = self._data_dir / RSA_PUBLIC_KEY_FILE
        with open(public_key_file, "wb") as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
    
    def get_public_key_pem(self) -> str:
        """
        Get public key in PEM format for frontend.
        
        Returns:
            PEM-encoded public key string
        """
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")
    
    def decrypt(self, encrypted_base64: str) -> str:
        """
        Decrypt data encrypted with public key.
        
        Args:
            encrypted_base64: Base64-encoded encrypted data
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ConfigDecryptionError: If decryption fails
        """
        if not encrypted_base64:
            return ""
        
        try:
            encrypted_data = base64.b64decode(encrypted_base64)
            plaintext = self._private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return plaintext.decode("utf-8")
        except Exception as e:
            raise ConfigDecryptionError(f"RSA decryption failed: {e}")


# Global encryption manager instance (lazy initialization)
_encryption_manager: Optional[EncryptionManager] = None
_rsa_encryption_manager: Optional[RSAEncryptionManager] = None


def get_encryption_manager(data_dir: str = "data") -> EncryptionManager:
    """Get or create the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager(data_dir=data_dir)
    return _encryption_manager


def get_rsa_encryption_manager(data_dir: str = "data") -> RSAEncryptionManager:
    """Get or create the global RSA encryption manager instance."""
    global _rsa_encryption_manager
    if _rsa_encryption_manager is None:
        _rsa_encryption_manager = RSAEncryptionManager(data_dir=data_dir)
    return _rsa_encryption_manager
