#!/usr/bin/env python3
"""
Script to create an initial API key for the Hybrid TTS system

Usage:
    python scripts/create_api_key.py <key_name>

Example:
    python scripts/create_api_key.py admin
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.auth import APIKeyManager
from cache.manager import cache_manager
import structlog

logger = structlog.get_logger()


def create_initial_api_key(name: str = "admin"):
    """Create an initial API key"""
    try:
        # Ensure Redis is connected
        cache_manager.redis_client.ping()
        logger.info("redis_connected")

        # Create API key
        public_key, full_api_key = APIKeyManager.create_api_key(name)

        print("\n" + "=" * 70)
        print("🔐 API Key Created Successfully!")
        print("=" * 70)
        print(f"\nPublic Key: {public_key}")
        print(f"Full API Key: {full_api_key}")
        print("\n⚠️  IMPORTANT:")
        print("  - Save this API key securely - it will NOT be shown again")
        print("  - Use it in the X-API-Key header for admin operations")
        print("  - Example: curl -H 'X-API-Key: <full_api_key>' ...")
        print("\n" + "=" * 70 + "\n")

        return full_api_key

    except Exception as e:
        logger.error("api_key_creation_failed", error=str(e))
        print(f"\n❌ Error creating API key: {e}")
        print("\nMake sure:")
        print("  - Redis is running (check config.py settings)")
        print("  - You're in the correct directory")
        print("  - All dependencies are installed")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_api_key.py <key_name>")
        print("Example: python scripts/create_api_key.py admin")
        sys.exit(1)

    key_name = sys.argv[1]
    create_initial_api_key(key_name)
