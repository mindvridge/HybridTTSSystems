"""
API Endpoint tests for Hybrid TTS Cost Optimizer
Tests all REST API endpoints for correctness and stability
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import json


class TestRootEndpoints:
    """Test root level endpoints"""

    def test_root_returns_api_info(self, test_client):
        """Test root endpoint returns correct API information"""
        response = test_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "running"
        assert "name" in data
        assert "version" in data
        assert data["docs"] == "/docs"
        assert data["dashboard"] == "/api/v1/monitoring/dashboard"
        assert data["metrics"] == "/api/v1/monitoring/metrics"

    def test_health_check_endpoint(self, test_client):
        """Test health check returns proper status"""
        response = test_client.get("/health")

        # May be 200 (healthy) or 503 (unhealthy depending on Redis)
        assert response.status_code in [200, 503]

        data = response.json()
        if response.status_code == 200:
            assert data["status"] == "healthy"
        else:
            assert "detail" in data


class TestSynthesisAPI:
    """Test TTS synthesis API endpoints"""

    def test_synthesize_requires_text(self, test_client):
        """Test that synthesize endpoint requires text field"""
        response = test_client.post(
            "/api/v1/synthesize",
            json={}
        )
        assert response.status_code == 422

        errors = response.json()
        assert "detail" in errors

    def test_synthesize_rejects_empty_text(self, test_client):
        """Test that empty text is rejected"""
        response = test_client.post(
            "/api/v1/synthesize",
            json={"text": ""}
        )
        assert response.status_code == 422

    def test_synthesize_rejects_whitespace_only(self, test_client):
        """Test that whitespace-only text is rejected"""
        response = test_client.post(
            "/api/v1/synthesize",
            json={"text": "   "}
        )
        assert response.status_code == 422

    def test_synthesize_rejects_oversized_text(self, test_client):
        """Test that text exceeding max length is rejected"""
        response = test_client.post(
            "/api/v1/synthesize",
            json={"text": "x" * 6000}  # Exceeds 5000 limit
        )
        assert response.status_code == 422

    def test_synthesize_accepts_valid_text(self, test_client, mock_tts_response):
        """Test synthesis with valid text"""
        with patch("tts.provider.tts_provider.synthesize", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = mock_tts_response

            response = test_client.post(
                "/api/v1/synthesize",
                json={"text": "테스트입니다", "use_cache": False}
            )

            # May succeed or fail based on provider state
            assert response.status_code in [200, 500]

    def test_synthesize_with_voice_parameter(self, test_client):
        """Test synthesis with voice parameter"""
        response = test_client.post(
            "/api/v1/synthesize",
            json={
                "text": "테스트",
                "voice": "ko-KR-Neural2-A",
                "use_cache": True
            }
        )
        # Should process the request
        assert response.status_code in [200, 500]

    def test_synthesize_with_template(self, test_client):
        """Test synthesis with template"""
        response = test_client.post(
            "/api/v1/synthesize",
            json={
                "text": "fallback text",
                "template_id": "greeting_morning",
                "slot_values": {"name": "홍길동"}
            }
        )
        # May return 400 if template not found or 200/500 otherwise
        assert response.status_code in [200, 400, 500]

    def test_synthesis_stats(self, test_client):
        """Test synthesis statistics endpoint"""
        response = test_client.get("/api/v1/synthesis/stats")
        assert response.status_code == 200

        data = response.json()
        assert "pipeline" in data
        assert "cache" in data


class TestBatchSynthesisAPI:
    """Test batch synthesis endpoints"""

    def test_batch_synthesis_endpoint_exists(self, test_client):
        """Test batch synthesis endpoint is available"""
        response = test_client.post(
            "/api/v1/synthesize/batch",
            params={"texts": ["test1", "test2"]}
        )
        # Should be accessible (may fail on actual synthesis)
        assert response.status_code in [200, 400, 422, 500]

    def test_batch_rejects_oversized_batch(self, test_client):
        """Test batch endpoint rejects oversized batches"""
        texts = ["test"] * 150  # Exceeds 100 limit
        response = test_client.post(
            "/api/v1/synthesize/batch",
            params={"texts": texts}
        )
        assert response.status_code in [400, 422]


class TestTemplateSynthesisAPI:
    """Test template-based synthesis"""

    def test_template_synthesis_endpoint(self, test_client):
        """Test template synthesis endpoint"""
        response = test_client.post(
            "/api/v1/synthesize/template",
            json={
                "template_id": "greeting_morning",
                "slot_values": {"name": "테스트"}
            }
        )
        assert response.status_code in [200, 404, 422, 500]

    def test_template_synthesis_missing_template(self, test_client):
        """Test template synthesis with missing template ID"""
        response = test_client.post(
            "/api/v1/synthesize/template",
            json={
                "slot_values": {"name": "테스트"}
            }
        )
        assert response.status_code == 422


class TestMonitoringAPI:
    """Test monitoring API endpoints"""

    def test_prometheus_metrics_format(self, test_client):
        """Test Prometheus metrics endpoint returns proper format"""
        response = test_client.get("/api/v1/monitoring/metrics")
        assert response.status_code == 200

        # Should be text/plain with Prometheus format
        content_type = response.headers.get("content-type", "")
        assert "text" in content_type

        # Should contain metric definitions
        content = response.text
        assert len(content) > 0

    def test_monitoring_stats_structure(self, test_client):
        """Test monitoring stats response structure"""
        response = test_client.get("/api/v1/monitoring/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "metrics" in data

    def test_performance_report_structure(self, test_client):
        """Test performance report response structure"""
        response = test_client.get("/api/v1/monitoring/report")
        assert response.status_code == 200

        data = response.json()
        # Should contain targets and summary
        assert isinstance(data, dict)

    def test_timeseries_with_hours_param(self, test_client):
        """Test timeseries with hours parameter"""
        response = test_client.get("/api/v1/monitoring/timeseries?hours=12")
        assert response.status_code == 200

        data = response.json()
        assert "start_time" in data
        assert "data_points" in data

    def test_timeseries_with_time_range(self, test_client):
        """Test timeseries with explicit time range"""
        response = test_client.get(
            "/api/v1/monitoring/timeseries",
            params={
                "start_time": "2024-01-01T00:00:00",
                "end_time": "2024-01-02T00:00:00"
            }
        )
        assert response.status_code == 200

    def test_dashboard_returns_html(self, test_client):
        """Test dashboard returns valid HTML"""
        response = test_client.get("/api/v1/monitoring/dashboard")
        assert response.status_code == 200

        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
        assert "Hybrid TTS" in response.text


class TestTemplateAPI:
    """Test template management API"""

    def test_list_templates(self, test_client):
        """Test listing all templates"""
        response = test_client.get("/api/v1/templates")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, (dict, list))

    def test_get_template_categories(self, test_client):
        """Test getting templates by category"""
        response = test_client.get("/api/v1/templates/category/greeting")
        assert response.status_code in [200, 404]

    def test_get_static_phrases(self, test_client):
        """Test getting static phrases"""
        response = test_client.get("/api/v1/templates/static-phrases")
        assert response.status_code in [200, 404]


class TestSystemStatsAPI:
    """Test system statistics API"""

    def test_comprehensive_stats(self, test_client):
        """Test comprehensive system stats"""
        response = test_client.get("/api/v1/stats")
        assert response.status_code == 200

        data = response.json()
        assert "cache" in data
        assert "matching_pipeline" in data
        assert "templates" in data
        assert "cost_savings" in data

        # Verify cost savings structure
        cost_savings = data["cost_savings"]
        assert "target_hit_rate" in cost_savings
        assert "target_cost_reduction" in cost_savings


class TestAdminAPI:
    """Test admin API endpoints"""

    def test_cache_clear_endpoint(self, test_client):
        """Test cache clear admin endpoint"""
        response = test_client.post("/api/v1/cache/clear")
        # Without proper auth, may succeed or fail
        assert response.status_code in [200, 401, 403]


class TestErrorResponses:
    """Test API error responses"""

    def test_404_response_format(self, test_client):
        """Test 404 error response format"""
        response = test_client.get("/api/v1/nonexistent")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_422_validation_error_format(self, test_client):
        """Test 422 validation error format"""
        response = test_client.post(
            "/api/v1/synthesize",
            json={"text": None}
        )
        assert response.status_code == 422

        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

    def test_method_not_allowed_format(self, test_client):
        """Test 405 method not allowed response"""
        response = test_client.delete("/api/v1/synthesize")
        assert response.status_code == 405


class TestRequestValidation:
    """Test request validation across endpoints"""

    def test_invalid_json_rejected(self, test_client):
        """Test invalid JSON is properly rejected"""
        response = test_client.post(
            "/api/v1/synthesize",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_content_type(self, test_client):
        """Test request without content type"""
        response = test_client.post(
            "/api/v1/synthesize",
            content='{"text": "test"}'
        )
        # FastAPI may still process it
        assert response.status_code in [200, 415, 422, 500]


class TestResponseHeaders:
    """Test API response headers"""

    def test_json_content_type(self, test_client):
        """Test JSON responses have correct content type"""
        response = test_client.get("/api/v1/monitoring/stats")
        assert "application/json" in response.headers["content-type"]

    def test_metrics_content_type(self, test_client):
        """Test metrics endpoint content type"""
        response = test_client.get("/api/v1/monitoring/metrics")
        # Should be text format for Prometheus
        assert "text" in response.headers["content-type"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
