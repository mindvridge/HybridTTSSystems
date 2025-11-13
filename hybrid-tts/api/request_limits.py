"""
Request Size Limits Middleware
"""
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import structlog

logger = structlog.get_logger()


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request size limits"""

    def __init__(self, app, max_size_mb: int = 10):
        """
        Initialize middleware

        Args:
            app: FastAPI app instance
            max_size_mb: Maximum request size in megabytes
        """
        super().__init__(app)
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        logger.info("request_size_limit_initialized", max_size_mb=max_size_mb)

    async def dispatch(self, request: Request, call_next):
        """Check request size before processing"""

        # Check Content-Length header
        content_length = request.headers.get("content-length")

        if content_length:
            content_length = int(content_length)

            if content_length > self.max_size:
                logger.warning(
                    "request_too_large",
                    content_length=content_length,
                    max_size=self.max_size,
                    endpoint=request.url.path,
                    client_ip=request.client.host if request.client else "unknown"
                )

                raise HTTPException(
                    status_code=413,
                    detail=f"Request body too large. Maximum size: {self.max_size / (1024 * 1024):.1f} MB"
                )

        response = await call_next(request)
        return response
