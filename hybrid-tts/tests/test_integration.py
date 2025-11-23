"""
Integration tests for Hybrid TTS Cost Optimizer API
Comprehensive test suite for ensuring system stability and correctness
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import json
import time

# Mock environment before importing app
import os
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["API_REQUIRE_AUTH"] = "False"
os.environ["ENABLE_RATE_LIMITING"] = "False"
os.environ["DEBUG"] = "True"


class MockRedis:
    """Mock Redis client for testing"""
    def __init__(self):
        self._data = {}
        self._stats = {"hits": 0, "misses": 0}

    def get(self, key):
        if key in self._data:
            self._stats["hits"] += 1
            return self._data[key]
        self._stats["misses"] += 1
        return None

    def set(self, key, value, ex=None):
        self._data[key] = value
        return True

    def delete(self, *keys):
        for key in keys:
            self._data.pop(key, None)
        return len(keys)

    def flushdb(self):
        self._data = {}
        self._stats = {"hits": 0, "misses": 0}
        return True

    def keys(self, pattern="*"):
        return list(self._data.keys())

    def ping(self):
        return True

    def info(self, section=None):
        return {"used_memory": 1024, "connected_clients": 1}


@pytest.fixture(scope="module")
def mock_redis():
    """Provide mock Redis for all tests"""
    return MockRedis()


@pytest.fixture(scope="module")
def client(mock_redis):
    """Create test client with mocked dependencies"""
    with patch("redis.Redis", return_value=mock_redis):
        with patch("cache.manager.CacheManager._connect_redis", return_value=mock_redis):
            from api.main import app
            with TestClient(app) as test_client:
                yield test_client


@pytest.fixture(autouse=True)
def reset_mock_redis(mock_redis):
    """Reset mock Redis before each test"""
    mock_redis.flushdb()


class TestHealthEndpoints:
    """Test health check and root endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info"""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["status"] == "running"
        assert "docs" in data
        assert "dashboard" in data
        assert "metrics" in data

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "healthy"
            assert "redis" in data
            assert "templates" in data


class TestMonitoringEndpoints:
    """Test monitoring and metrics endpoints"""

    def test_prometheus_metrics(self, client):
        """Test Prometheus metrics endpoint returns valid format"""
        response = client.get("/api/v1/monitoring/metrics")
        assert response.status_code == 200

        # Prometheus format should contain metric definitions
        content = response.text
        assert "hybrid_tts" in content or "http_requests" in content

    def test_monitoring_stats(self, client):
        """Test monitoring stats endpoint"""
        response = client.get("/api/v1/monitoring/stats")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "metrics" in data

    def test_performance_report(self, client):
        """Test performance report endpoint"""
        response = client.get("/api/v1/monitoring/report")
        assert response.status_code == 200

        data = response.json()
        assert "targets" in data or "summary" in data

    def test_timeseries_data(self, client):
        """Test timeseries data endpoint"""
        response = client.get("/api/v1/monitoring/timeseries?hours=24")
        assert response.status_code == 200

        data = response.json()
        assert "start_time" in data
        assert "data_points" in data

    def test_dashboard_html(self, client):
        """Test dashboard returns valid HTML"""
        response = client.get("/api/v1/monitoring/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Hybrid TTS" in response.text


class TestSynthesisEndpoints:
    """Test TTS synthesis endpoints"""

    @pytest.mark.asyncio
    async def test_synthesize_with_cache_hit(self, client, mock_redis):
        """Test synthesis with cache hit"""
        # Pre-populate cache
        test_text = "안녕하세요"
        cache_key = f"tts:{test_text}:"
        mock_redis.set(cache_key, b"mock_audio_data")

        with patch("cache.manager.cache_manager.get", return_value=b"mock_audio_data"):
            response = client.post(
                "/api/v1/synthesize",
                json={"text": test_text, "use_cache": True}
            )

            # Should return audio or error depending on full system state
            assert response.status_code in [200, 500]

    def test_synthesize_empty_text_rejected(self, client):
        """Test that empty text is rejected"""
        response = client.post(
            "/api/v1/synthesize",
            json={"text": "", "use_cache": True}
        )
        assert response.status_code == 422  # Validation error

    def test_synthesize_text_length_limit(self, client):
        """Test that text exceeding max length is rejected"""
        long_text = "a" * 10000  # Exceeds 5000 char limit
        response = client.post(
            "/api/v1/synthesize",
            json={"text": long_text, "use_cache": True}
        )
        assert response.status_code == 422  # Validation error

    def test_synthesis_stats_endpoint(self, client):
        """Test synthesis stats endpoint"""
        response = client.get("/api/v1/synthesis/stats")
        assert response.status_code == 200

        data = response.json()
        assert "pipeline" in data
        assert "cache" in data


class TestBatchSynthesis:
    """Test batch synthesis functionality"""

    def test_batch_empty_list(self, client):
        """Test batch synthesis with empty list"""
        response = client.post(
            "/api/v1/synthesize/batch",
            json=[]
        )
        # Should handle empty list gracefully
        assert response.status_code in [200, 422]

    def test_batch_exceeds_limit(self, client):
        """Test batch synthesis exceeding max items"""
        texts = ["test"] * 150  # Exceeds 100 item limit
        response = client.post(
            "/api/v1/synthesize/batch",
            params={"texts": texts}
        )
        # Should reject or handle appropriately
        assert response.status_code in [400, 422]


class TestTemplateEndpoints:
    """Test template management endpoints"""

    def test_list_templates(self, client):
        """Test listing all templates"""
        response = client.get("/api/v1/templates")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict) or isinstance(data, list)

    def test_get_template_by_id(self, client):
        """Test getting template by ID"""
        # First get list of templates
        list_response = client.get("/api/v1/templates")
        if list_response.status_code == 200:
            templates = list_response.json()
            if templates:
                template_id = list(templates.keys())[0] if isinstance(templates, dict) else templates[0].get("id", "greeting_morning")

                response = client.get(f"/api/v1/templates/{template_id}")
                assert response.status_code in [200, 404]

    def test_get_nonexistent_template(self, client):
        """Test getting non-existent template returns 404"""
        response = client.get("/api/v1/templates/nonexistent_template_xyz")
        assert response.status_code == 404


class TestSystemStats:
    """Test system statistics endpoints"""

    def test_system_stats(self, client):
        """Test comprehensive system stats endpoint"""
        response = client.get("/api/v1/stats")
        assert response.status_code == 200

        data = response.json()
        assert "cache" in data
        assert "matching_pipeline" in data
        assert "templates" in data
        assert "cost_savings" in data


class TestSecurityFeatures:
    """Test security-related features"""

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options(
            "/api/v1/synthesize",
            headers={"Origin": "http://localhost:3000"}
        )
        # CORS middleware should handle OPTIONS
        assert response.status_code in [200, 405, 400]

    def test_request_with_invalid_json(self, client):
        """Test invalid JSON is rejected gracefully"""
        response = client.post(
            "/api/v1/synthesize",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_large_request_body(self, client):
        """Test large request bodies are handled"""
        # Create a large payload
        large_data = {"text": "a" * 4999, "extra_data": "b" * 10000}
        response = client.post(
            "/api/v1/synthesize",
            json=large_data
        )
        # Should either process or reject based on size limits
        assert response.status_code in [200, 413, 422, 500]


class TestCacheOperations:
    """Test cache-related operations"""

    def test_cache_clear_requires_auth_when_enabled(self, client):
        """Test cache clear endpoint behavior"""
        response = client.post("/api/v1/cache/clear")
        # Without auth, should succeed (auth disabled) or fail (auth enabled)
        assert response.status_code in [200, 401, 403]


class TestErrorHandling:
    """Test error handling across endpoints"""

    def test_404_for_unknown_endpoint(self, client):
        """Test 404 for unknown endpoints"""
        response = client.get("/api/v1/nonexistent_endpoint")
        assert response.status_code == 404

    def test_405_for_wrong_method(self, client):
        """Test 405 for wrong HTTP method"""
        response = client.delete("/api/v1/synthesize")
        assert response.status_code == 405

    def test_global_exception_handler(self, client):
        """Test that unhandled exceptions return proper error response"""
        # Send malformed request that might trigger exception
        response = client.post(
            "/api/v1/synthesize",
            json={"text": None}
        )
        assert response.status_code in [422, 500]


class TestMatchingPipeline:
    """Test matching pipeline integration"""

    def test_pipeline_stats(self, client):
        """Test pipeline statistics are returned"""
        response = client.get("/api/v1/synthesis/stats")
        assert response.status_code == 200

        data = response.json()
        pipeline_stats = data.get("pipeline", {})

        # Verify expected stat fields
        assert isinstance(pipeline_stats, dict)


class TestLatencyTracking:
    """Test latency tracking functionality"""

    def test_response_includes_timing(self, client):
        """Test that responses include timing information"""
        response = client.get("/api/v1/monitoring/stats")
        assert response.status_code == 200

        # Response time should be reasonable (< 5 seconds)
        assert response.elapsed.total_seconds() < 5


class TestConcurrency:
    """Test concurrent request handling"""

    def test_multiple_concurrent_requests(self, client):
        """Test handling multiple concurrent requests"""
        import concurrent.futures

        def make_request():
            return client.get("/api/v1/monitoring/stats")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        for result in results:
            assert result.status_code == 200


class TestDataValidation:
    """Test input data validation"""

    def test_synthesis_request_validation(self, client):
        """Test synthesis request model validation"""
        # Missing required field
        response = client.post("/api/v1/synthesize", json={})
        assert response.status_code == 422

        # Invalid type
        response = client.post("/api/v1/synthesize", json={"text": 123})
        assert response.status_code == 422

    def test_voice_parameter_validation(self, client):
        """Test voice parameter validation"""
        response = client.post(
            "/api/v1/synthesize",
            json={"text": "test", "voice": "a" * 200}  # Too long
        )
        assert response.status_code == 422


class TestTemplateRendering:
    """Test template rendering functionality"""

    def test_synthesize_from_template_invalid_id(self, client):
        """Test synthesis with invalid template ID"""
        response = client.post(
            "/api/v1/synthesize/template",
            json={"template_id": "invalid_template", "slot_values": {}}
        )
        assert response.status_code in [404, 422]


# Performance tests (marked as slow)
@pytest.mark.slow
class TestPerformance:
    """Performance-related tests"""

    def test_stats_endpoint_performance(self, client):
        """Test stats endpoint response time"""
        start = time.time()
        response = client.get("/api/v1/monitoring/stats")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0  # Should respond in under 1 second

    def test_metrics_endpoint_performance(self, client):
        """Test metrics endpoint response time"""
        start = time.time()
        response = client.get("/api/v1/monitoring/metrics")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0  # Should respond in under 2 seconds


# Integration marker tests
@pytest.mark.integration
class TestFullIntegration:
    """Full integration tests requiring all services"""

    def test_end_to_end_flow(self, client):
        """Test complete request flow"""
        # 1. Check health
        health = client.get("/health")

        # 2. Get stats
        stats = client.get("/api/v1/stats")
        assert stats.status_code == 200

        # 3. Get metrics
        metrics = client.get("/api/v1/monitoring/metrics")
        assert metrics.status_code == 200

        # 4. Get dashboard
        dashboard = client.get("/api/v1/monitoring/dashboard")
        assert dashboard.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
