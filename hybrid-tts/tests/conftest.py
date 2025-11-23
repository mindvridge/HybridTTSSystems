"""
Pytest configuration and shared fixtures for Hybrid TTS tests
"""
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables before any imports
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("API_REQUIRE_AUTH", "False")
os.environ.setdefault("ENABLE_RATE_LIMITING", "False")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ENABLE_METRICS", "True")


class MockRedisClient:
    """
    Mock Redis client for testing without actual Redis connection
    """
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._ttls: Dict[str, int] = {}
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Any:
        value = self._store.get(key)
        if value is not None:
            self._hit_count += 1
        else:
            self._miss_count += 1
        return value

    def set(self, key: str, value: Any, ex: int = None) -> bool:
        self._store[key] = value
        if ex:
            self._ttls[key] = ex
        return True

    def setex(self, key: str, time: int, value: Any) -> bool:
        self._store[key] = value
        self._ttls[key] = time
        return True

    def delete(self, *keys) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    def exists(self, key: str) -> bool:
        return key in self._store

    def keys(self, pattern: str = "*") -> list:
        if pattern == "*":
            return list(self._store.keys())
        # Simple pattern matching
        import fnmatch
        return [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]

    def flushdb(self) -> bool:
        self._store.clear()
        self._ttls.clear()
        self._hit_count = 0
        self._miss_count = 0
        return True

    def flushall(self) -> bool:
        return self.flushdb()

    def ping(self) -> bool:
        return True

    def info(self, section: str = None) -> Dict[str, Any]:
        return {
            "used_memory": len(str(self._store)),
            "used_memory_human": "1K",
            "connected_clients": 1,
            "keyspace_hits": self._hit_count,
            "keyspace_misses": self._miss_count,
        }

    def dbsize(self) -> int:
        return len(self._store)

    def scan_iter(self, match: str = "*", count: int = 100):
        return iter(self.keys(match))

    def pipeline(self):
        return MockRedisPipeline(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockRedisPipeline:
    """Mock Redis pipeline for batch operations"""
    def __init__(self, redis_client: MockRedisClient):
        self._client = redis_client
        self._commands = []

    def set(self, key: str, value: Any, ex: int = None):
        self._commands.append(("set", key, value, ex))
        return self

    def get(self, key: str):
        self._commands.append(("get", key))
        return self

    def delete(self, key: str):
        self._commands.append(("delete", key))
        return self

    def execute(self) -> list:
        results = []
        for cmd in self._commands:
            if cmd[0] == "set":
                results.append(self._client.set(cmd[1], cmd[2], cmd[3]))
            elif cmd[0] == "get":
                results.append(self._client.get(cmd[1]))
            elif cmd[0] == "delete":
                results.append(self._client.delete(cmd[1]))
        self._commands.clear()
        return results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture(scope="session")
def mock_redis():
    """Session-scoped mock Redis client"""
    return MockRedisClient()


@pytest.fixture
def clean_mock_redis(mock_redis):
    """Clean mock Redis for each test"""
    mock_redis.flushdb()
    return mock_redis


@pytest.fixture(scope="session")
def test_client(mock_redis):
    """
    Create FastAPI TestClient with mocked dependencies
    Session-scoped to improve test performance
    """
    with patch("redis.Redis", return_value=mock_redis):
        with patch("redis.from_url", return_value=mock_redis):
            # Patch the cache manager's Redis connection
            with patch("cache.manager.CacheManager._connect_redis", return_value=mock_redis):
                from fastapi.testclient import TestClient
                from api.main import app
                with TestClient(app) as client:
                    yield client


@pytest.fixture
def sample_texts():
    """Sample texts for testing"""
    return {
        "korean": [
            "안녕하세요",
            "감사합니다",
            "잔액을 확인해드리겠습니다",
            "거래가 완료되었습니다",
            "좋은 하루 되세요",
        ],
        "english": [
            "Hello",
            "Thank you",
            "Your balance is",
            "Transaction complete",
            "Have a nice day",
        ],
        "mixed": [
            "안녕하세요, your balance is 10000원입니다",
            "Hello, 감사합니다",
        ]
    }


@pytest.fixture
def sample_templates():
    """Sample template data for testing"""
    return {
        "greeting_morning": {
            "template": "좋은 아침입니다, {name}님",
            "slots": ["name"],
            "category": "greeting"
        },
        "balance_inquiry": {
            "template": "{name}님의 잔액은 {amount}원입니다",
            "slots": ["name", "amount"],
            "category": "banking"
        }
    }


@pytest.fixture
def mock_tts_response():
    """Mock TTS response data"""
    return b"MOCK_AUDIO_DATA_" + b"\x00" * 1000


@pytest.fixture
def mock_metrics():
    """Mock metrics data"""
    return {
        "total_requests": 100,
        "cache_hits": 80,
        "cache_misses": 20,
        "cache_hit_rate": 0.8,
        "estimated_cost_reduction": 0.72,
        "avg_latency_ms": 15.5,
        "method_distribution": {
            "exact_rate": 0.6,
            "fuzzy_rate": 0.15,
            "semantic_rate": 0.05,
            "tts_rate": 0.2
        }
    }


# Pytest configuration
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers"""
    # Add integration marker to tests in test_integration.py
    for item in items:
        if "test_integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def reset_prometheus_metrics():
    """Reset Prometheus metrics between tests to avoid pollution"""
    yield
    # Metrics reset handled by test isolation


@pytest.fixture
def api_headers():
    """Common API headers for testing"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


@pytest.fixture
def auth_headers(api_headers):
    """API headers with authentication"""
    headers = api_headers.copy()
    headers["X-API-Key"] = "test-api-key"
    return headers
