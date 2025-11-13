"""
API Key Authentication System
"""
from fastapi import HTTPException, Header, Depends
from typing import Optional
import hashlib
import structlog
from cache.manager import cache_manager

logger = structlog.get_logger()


class APIKeyManager:
    """Manage API keys stored in Redis"""

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def create_api_key(name: str) -> tuple[str, str]:
        """
        Create new API key

        Args:
            name: Identifier for the API key (e.g., "admin", "service1")

        Returns:
            (public_key, full_api_key): Public identifier and full key with secret
        """
        import secrets

        # Generate random secret (32 bytes = 256 bits)
        secret = secrets.token_urlsafe(32)

        # Hash for storage
        secret_hash = APIKeyManager.hash_key(secret)

        # Public key (for logging/reference)
        public_key = f"hybrid-tts_{name}_{secrets.token_hex(8)}"

        # Store in Redis: key -> hash
        cache_manager.redis_client.hset(
            "api_keys",
            public_key,
            secret_hash
        )

        logger.info("api_key_created", name=name, public_key=public_key)

        # Return both public key and full API key (public:secret)
        full_api_key = f"{public_key}:{secret}"

        return public_key, full_api_key

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """
        Validate API key against stored hash

        Args:
            api_key: Full API key in format "public_key:secret"

        Returns:
            True if valid, False otherwise
        """
        try:
            # Extract public key and secret
            parts = api_key.split(':')
            if len(parts) != 2:
                logger.warning("api_key_invalid_format", format="missing colon separator")
                return False

            public_key, secret = parts

            # Get stored hash from Redis
            stored_hash = cache_manager.redis_client.hget("api_keys", public_key)

            if not stored_hash:
                logger.warning("api_key_not_found", public_key=public_key)
                return False

            # Decode if bytes
            if isinstance(stored_hash, bytes):
                stored_hash = stored_hash.decode('utf-8')

            # Hash provided secret
            secret_hash = APIKeyManager.hash_key(secret)

            # Compare hashes
            is_valid = secret_hash == stored_hash

            if is_valid:
                logger.debug("api_key_validated", public_key=public_key)
            else:
                logger.warning("api_key_invalid_secret", public_key=public_key)

            return is_valid

        except Exception as e:
            logger.error("api_key_validation_error", error=str(e))
            return False

    @staticmethod
    def revoke_api_key(public_key: str) -> bool:
        """
        Revoke an API key

        Args:
            public_key: Public part of the API key

        Returns:
            True if revoked, False if not found
        """
        try:
            result = cache_manager.redis_client.hdel("api_keys", public_key)

            if result:
                logger.info("api_key_revoked", public_key=public_key)
                return True
            else:
                logger.warning("api_key_not_found_for_revocation", public_key=public_key)
                return False

        except Exception as e:
            logger.error("api_key_revocation_error", error=str(e))
            return False

    @staticmethod
    def list_api_keys() -> list[str]:
        """
        List all API key public identifiers

        Returns:
            List of public key identifiers
        """
        try:
            keys = cache_manager.redis_client.hkeys("api_keys")
            # Decode if bytes
            return [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
        except Exception as e:
            logger.error("api_key_list_error", error=str(e))
            return []


# Dependency for authentication
async def verify_api_key(
    x_api_key: Optional[str] = Header(None, description="API key in format 'public:secret'")
) -> str:
    """
    Verify API key from X-API-Key header

    Args:
        x_api_key: API key from header

    Returns:
        Public key part of the API key

    Raises:
        HTTPException: 401 if missing or invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not APIKeyManager.validate_api_key(x_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Return public key part for logging
    public_key = x_api_key.split(':')[0]
    return public_key


# Optional authentication (doesn't fail if missing)
async def optional_api_key(
    x_api_key: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Optional API key validation - doesn't fail if missing

    Returns:
        Public key if valid, None if missing or invalid
    """
    if not x_api_key:
        return None

    if APIKeyManager.validate_api_key(x_api_key):
        return x_api_key.split(':')[0]

    return None
