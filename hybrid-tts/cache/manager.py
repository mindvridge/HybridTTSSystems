"""
Audio Cache Manager with Redis backend
Implements LRU eviction policy and TTL management
"""
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import redis
import structlog
from config import settings

logger = structlog.get_logger()


class CacheManager:
    """
    Manages audio file caching with Redis as metadata store
    and local filesystem for audio storage
    """

    def __init__(self):
        """Initialize cache manager with Redis connection"""
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
        self.storage_path = Path(settings.CACHE_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Cache stats
        self.stats = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0,
        }

        logger.info("cache_manager_initialized", storage_path=str(self.storage_path))

    def _generate_cache_key(self, text: str, voice: str = "", **params) -> str:
        """
        Generate unique cache key from text and parameters
        Uses SHA256 hash for consistent key generation
        """
        # Normalize text (lowercase, strip whitespace)
        normalized_text = text.lower().strip()

        # Create key components
        key_data = {
            "text": normalized_text,
            "voice": voice,
            **params,
        }

        # Generate hash
        key_string = json.dumps(key_data, sort_keys=True)
        hash_key = hashlib.sha256(key_string.encode()).hexdigest()

        return f"tts:audio:{hash_key}"

    def _get_audio_path(self, cache_key: str) -> Path:
        """Get filesystem path for audio file"""
        # Extract hash from cache key
        hash_value = cache_key.split(":")[-1]
        # Use first 2 chars for subdirectory (better file distribution)
        subdir = hash_value[:2]
        audio_dir = self.storage_path / subdir
        audio_dir.mkdir(exist_ok=True)

        return audio_dir / f"{hash_value}.{settings.AUDIO_FORMAT}"

    def get(self, text: str, voice: str = "", **params) -> Optional[bytes]:
        """
        Retrieve audio from cache
        Returns audio bytes if found, None otherwise
        """
        self.stats["total_requests"] += 1
        cache_key = self._generate_cache_key(text, voice, **params)

        # Check if key exists in Redis
        metadata_str = self.redis_client.get(cache_key)

        if not metadata_str:
            self.stats["misses"] += 1
            logger.debug("cache_miss", text=text[:50])
            return None

        # Parse metadata
        metadata = json.loads(metadata_str)
        audio_path = Path(metadata["audio_path"])

        # Check if file exists
        if not audio_path.exists():
            logger.warning("cache_inconsistency", cache_key=cache_key, path=str(audio_path))
            self.redis_client.delete(cache_key)
            self.stats["misses"] += 1
            return None

        # Read and return audio
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        # Update access time (for LRU)
        metadata["last_access"] = datetime.utcnow().isoformat()
        metadata["access_count"] = metadata.get("access_count", 0) + 1
        self.redis_client.setex(
            cache_key,
            timedelta(days=settings.REDIS_TTL_DAYS),
            json.dumps(metadata),
        )

        self.stats["hits"] += 1
        logger.debug(
            "cache_hit",
            text=text[:50],
            access_count=metadata["access_count"],
        )

        return audio_data

    def set(
        self, text: str, audio_data: bytes, voice: str = "", **params
    ) -> bool:
        """
        Store audio in cache with metadata
        Returns True if successful
        """
        cache_key = self._generate_cache_key(text, voice, **params)
        audio_path = self._get_audio_path(cache_key)

        try:
            # Check cache size limits
            if not self._check_cache_limits():
                self._evict_lru()

            # Write audio to disk
            with open(audio_path, "wb") as f:
                f.write(audio_data)

            # Store metadata in Redis
            metadata = {
                "text": text,
                "voice": voice,
                "audio_path": str(audio_path),
                "audio_size": len(audio_data),
                "created_at": datetime.utcnow().isoformat(),
                "last_access": datetime.utcnow().isoformat(),
                "access_count": 0,
                "params": params,
            }

            self.redis_client.setex(
                cache_key,
                timedelta(days=settings.REDIS_TTL_DAYS),
                json.dumps(metadata),
            )

            logger.info(
                "cache_stored",
                text=text[:50],
                size=len(audio_data),
                path=str(audio_path),
            )

            return True

        except Exception as e:
            logger.error("cache_store_failed", error=str(e), text=text[:50])
            # Clean up partial write
            if audio_path.exists():
                audio_path.unlink()
            return False

    def _check_cache_limits(self) -> bool:
        """Check if cache is within configured limits"""
        # Count total cached items
        total_keys = len(self.redis_client.keys("tts:audio:*"))

        if total_keys >= settings.MAX_CACHE_CLIPS:
            logger.warning("cache_limit_reached", total_keys=total_keys)
            return False

        # Check memory usage (approximate)
        total_size_mb = self._get_total_cache_size_mb()
        if total_size_mb >= settings.MEMORY_LIMIT_MB:
            logger.warning("cache_memory_limit", size_mb=total_size_mb)
            return False

        return True

    def _get_total_cache_size_mb(self) -> float:
        """Calculate total cache size in MB"""
        total_size = 0
        for audio_file in self.storage_path.rglob(f"*.{settings.AUDIO_FORMAT}"):
            total_size += audio_file.stat().st_size

        return total_size / (1024 * 1024)

    def _evict_lru(self, count: int = 10):
        """
        Evict least recently used items from cache
        Uses LRU policy based on last_access timestamp
        """
        logger.info("evicting_lru_items", count=count)

        # Get all cache keys
        all_keys = self.redis_client.keys("tts:audio:*")

        # Get metadata for all keys
        items = []
        for key in all_keys:
            metadata_str = self.redis_client.get(key)
            if metadata_str:
                metadata = json.loads(metadata_str)
                items.append((key, metadata))

        # Sort by last access time (oldest first)
        items.sort(key=lambda x: x[1].get("last_access", ""))

        # Evict oldest items
        evicted = 0
        for key, metadata in items[:count]:
            audio_path = Path(metadata["audio_path"])
            if audio_path.exists():
                audio_path.unlink()

            self.redis_client.delete(key)
            evicted += 1

        logger.info("evicted_items", count=evicted)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_keys = len(self.redis_client.keys("tts:audio:*"))
        total_size_mb = self._get_total_cache_size_mb()

        hit_rate = 0.0
        if self.stats["total_requests"] > 0:
            hit_rate = self.stats["hits"] / self.stats["total_requests"]

        return {
            "total_cached_items": total_keys,
            "cache_size_mb": round(total_size_mb, 2),
            "max_clips": settings.MAX_CACHE_CLIPS,
            "max_size_mb": settings.MEMORY_LIMIT_MB,
            "cache_hit_rate": round(hit_rate, 4),
            "total_hits": self.stats["hits"],
            "total_misses": self.stats["misses"],
            "total_requests": self.stats["total_requests"],
        }

    def clear(self):
        """Clear entire cache (use with caution)"""
        logger.warning("clearing_entire_cache")

        # Delete all Redis keys
        all_keys = self.redis_client.keys("tts:audio:*")
        if all_keys:
            self.redis_client.delete(*all_keys)

        # Delete all audio files
        for audio_file in self.storage_path.rglob(f"*.{settings.AUDIO_FORMAT}"):
            audio_file.unlink()

        # Reset stats
        self.stats = {"hits": 0, "misses": 0, "total_requests": 0}

        logger.info("cache_cleared")

    def warm_up(self, phrases: list[tuple[str, bytes]], voice: str = ""):
        """
        Pre-populate cache with frequently used phrases
        phrases: list of (text, audio_bytes) tuples
        """
        logger.info("warming_up_cache", phrase_count=len(phrases))

        for text, audio_data in phrases:
            self.set(text, audio_data, voice)

        logger.info("cache_warmup_complete")


# Global cache manager instance
cache_manager = CacheManager()
