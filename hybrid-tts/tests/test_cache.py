"""
Unit tests for cache manager
"""
import pytest
from cache.manager import CacheManager


@pytest.fixture
def cache_manager():
    """Create cache manager instance for testing"""
    manager = CacheManager()
    # Clear cache before each test
    manager.clear()
    return manager


class TestCacheManager:
    """Test cache management functionality"""

    def test_cache_set_and_get(self, cache_manager):
        text = "테스트 문구입니다"
        audio_data = b"fake_audio_data"

        # Store in cache
        success = cache_manager.set(text, audio_data)
        assert success is True

        # Retrieve from cache
        retrieved = cache_manager.get(text)
        assert retrieved == audio_data

    def test_cache_miss(self, cache_manager):
        result = cache_manager.get("존재하지 않는 문구")
        assert result is None

    def test_cache_with_voice_parameter(self, cache_manager):
        text = "안녕하세요"
        audio1 = b"voice1_audio"
        audio2 = b"voice2_audio"

        # Store with different voices
        cache_manager.set(text, audio1, voice="voice1")
        cache_manager.set(text, audio2, voice="voice2")

        # Should retrieve correct audio for each voice
        assert cache_manager.get(text, voice="voice1") == audio1
        assert cache_manager.get(text, voice="voice2") == audio2

    def test_cache_stats(self, cache_manager):
        # Perform some operations
        cache_manager.set("text1", b"audio1")
        cache_manager.get("text1")  # Hit
        cache_manager.get("text2")  # Miss

        stats = cache_manager.get_stats()

        assert stats["total_requests"] == 2
        assert stats["total_hits"] >= 1
        assert stats["total_misses"] >= 1
        assert "cache_hit_rate" in stats

    def test_cache_clear(self, cache_manager):
        # Add some data
        cache_manager.set("text1", b"audio1")
        cache_manager.set("text2", b"audio2")

        # Clear cache
        cache_manager.clear()

        # Verify cache is empty
        assert cache_manager.get("text1") is None
        assert cache_manager.get("text2") is None

        stats = cache_manager.get_stats()
        assert stats["total_cached_items"] == 0
