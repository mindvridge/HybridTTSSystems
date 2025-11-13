"""
Middleware for request tracking and monitoring
"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram
import structlog

logger = structlog.get_logger()

# Prometheus metrics for HTTP requests
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track all HTTP requests
    Collects metrics for monitoring and observability
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Get endpoint path
        endpoint = request.url.path

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

            # Calculate latency
            latency = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=request.method, endpoint=endpoint, status=status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=request.method, endpoint=endpoint
            ).observe(latency)

            # Log request
            logger.info(
                "http_request",
                method=request.method,
                endpoint=endpoint,
                status=status_code,
                latency_ms=latency * 1000,
            )

            return response

        except Exception as e:
            # Record error
            latency = time.time() - start_time

            http_requests_total.labels(
                method=request.method, endpoint=endpoint, status=500
            ).inc()

            http_request_duration_seconds.labels(
                method=request.method, endpoint=endpoint
            ).observe(latency)

            logger.error(
                "http_request_error",
                method=request.method,
                endpoint=endpoint,
                error=str(e),
                latency_ms=latency * 1000,
            )

            # Re-raise the exception
            raise
