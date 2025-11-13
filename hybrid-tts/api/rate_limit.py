"""
Rate limiting middleware for API protection
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)

# Define rate limit keys for easy reference
LIMITS = {
    "public_read": "100/minute",           # GET endpoints, no resources
    "public_write": "20/minute",           # POST templates/render
    "synthesis": "10/minute",              # POST /synthesize
    "batch": "5/minute",                   # POST /synthesize/batch
    "admin": "5/hour",                     # Admin operations
    "monitoring": "10/minute",             # Monitoring endpoints
}


# Custom error handler
async def rate_limit_error_handler(request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors"""
    logger.warning(
        "rate_limit_exceeded",
        endpoint=request.url.path,
        limit=str(exc.detail),
        client_ip=get_remote_address(request),
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "error": "TOO_MANY_REQUESTS"
        }
    )
