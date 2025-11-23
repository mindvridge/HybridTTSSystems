# Testing Guide for Hybrid TTS Cost Optimizer

This document describes the testing infrastructure and how to run tests for the Hybrid TTS Cost Optimizer.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── test_cache.py            # Unit tests for cache manager
├── test_matching.py         # Unit tests for matching pipeline
├── test_templates.py        # Unit tests for template system
├── test_integration.py      # Integration tests for full system
└── test_api_endpoints.py    # API endpoint tests
```

## Test Categories

### Unit Tests
Unit tests focus on individual components in isolation:
- **test_cache.py**: Cache manager operations (set, get, clear, stats)
- **test_matching.py**: Matching pipeline (exact, fuzzy, semantic matching)
- **test_templates.py**: Template loading and rendering

### Integration Tests
Integration tests verify components working together:
- **test_integration.py**: End-to-end API tests, concurrent request handling
- **test_api_endpoints.py**: API contract verification, error handling

## Running Tests

### Run All Tests
```bash
cd hybrid-tts
pytest
```

### Run with Coverage
```bash
pytest --cov=. --cov-report=html --cov-report=term-missing
```

### Run Specific Test Categories
```bash
# Run only unit tests
pytest -m "not integration"

# Run only integration tests
pytest -m integration

# Run only fast tests (exclude slow)
pytest -m "not slow"
```

### Run Specific Test Files
```bash
# Run cache tests
pytest tests/test_cache.py -v

# Run API endpoint tests
pytest tests/test_api_endpoints.py -v

# Run integration tests
pytest tests/test_integration.py -v
```

### Run with Verbose Output
```bash
pytest -v --tb=long
```

## Test Configuration

### Environment Variables
Tests use mock Redis by default. Set these environment variables for testing:

```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export API_REQUIRE_AUTH=False
export ENABLE_RATE_LIMITING=False
export DEBUG=True
```

### pytest.ini
The `pytest.ini` file contains test configuration:
- Test paths
- Markers for categorizing tests
- Async mode configuration
- Warning filters

## Writing New Tests

### Using Fixtures
Common fixtures are defined in `conftest.py`:

```python
def test_example(test_client, mock_redis, sample_texts):
    # test_client: FastAPI TestClient
    # mock_redis: Mock Redis instance
    # sample_texts: Sample text data for testing
    response = test_client.get("/health")
    assert response.status_code == 200
```

### Test Markers
Use markers to categorize tests:

```python
import pytest

@pytest.mark.slow
def test_performance_benchmark():
    # Long-running test
    pass

@pytest.mark.integration
def test_end_to_end_flow():
    # Integration test
    pass
```

## Mocking

### Mock Redis
Tests use a mock Redis client that simulates Redis operations in memory:

```python
from tests.conftest import MockRedisClient

mock_redis = MockRedisClient()
mock_redis.set("key", "value")
assert mock_redis.get("key") == "value"
```

### Mock TTS Provider
For tests that need TTS synthesis:

```python
from unittest.mock import patch, AsyncMock

@patch("tts.provider.tts_provider.synthesize", new_callable=AsyncMock)
def test_synthesis(mock_synth):
    mock_synth.return_value = b"mock_audio_data"
    # Test synthesis endpoint
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run tests
        run: pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Test Best Practices

1. **Isolate tests**: Each test should be independent
2. **Use fixtures**: Share common setup through fixtures
3. **Mock external dependencies**: Don't rely on external services
4. **Test edge cases**: Include error scenarios and boundary conditions
5. **Keep tests fast**: Mark slow tests with `@pytest.mark.slow`
6. **Descriptive names**: Test names should describe what they test
