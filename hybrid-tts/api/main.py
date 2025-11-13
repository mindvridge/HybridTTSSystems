"""
Main FastAPI application for Hybrid TTS Cost Optimizer
"""
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from contextlib import asynccontextmanager

from config import settings
from cache.manager import cache_manager
from matching.pipeline import matching_pipeline
from templates.loader import template_manager
from monitoring import metrics_collector
from api.middleware import MonitoringMiddleware

# Import security components
from api.rate_limit import limiter, LIMITS, rate_limit_error_handler
from api.auth import verify_api_key, APIKeyManager
from api.security_headers import SecurityHeadersMiddleware
from api.request_limits import RequestSizeLimitMiddleware
from api.audit_log import AuditLog, log_admin_operation
from slowapi.errors import RateLimitExceeded

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events"""
    # Startup
    logger.info("starting_hybrid_tts_api", version=settings.APP_VERSION)

    # Load templates
    if template_manager.template_file.exists():
        template_manager.load_templates()
        logger.info("templates_loaded", count=len(template_manager.templates))

        # Warm up matching pipeline with static phrases
        static_phrases = template_manager.get_all_static_phrases()
        if static_phrases:
            matching_pipeline.bulk_add_phrases(static_phrases)
            logger.info("pipeline_warmed_up", phrase_count=len(static_phrases))

    # Initialize monitoring
    logger.info("monitoring_initialized", metrics_enabled=settings.ENABLE_METRICS)

    yield

    # Shutdown
    logger.info("shutting_down_hybrid_tts_api")

    # Flush metrics on shutdown
    if settings.ENABLE_METRICS:
        metrics_collector.flush()
        logger.info("metrics_flushed_on_shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Hybrid TTS Cost Optimizer - 70-90% cost reduction through intelligent caching",
    lifespan=lifespan,
)

# Security: Rate Limiting
if settings.ENABLE_RATE_LIMITING:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_error_handler)
    logger.info("rate_limiting_enabled", limits=LIMITS)

# Security: Request Size Limits
app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=settings.MAX_REQUEST_SIZE_MB)
logger.info("request_size_limits_enabled", max_size_mb=settings.MAX_REQUEST_SIZE_MB)

# Security: Security Headers
if settings.ENABLE_SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("security_headers_enabled")

# CORS middleware - Restrict origins in production
cors_origins = settings.CORS_ORIGINS.split(',') if settings.CORS_ORIGINS else ["*"]
if settings.DEBUG:
    # In development, be more permissive
    cors_origins = ["*"]
    logger.warning("cors_permissive_mode", message="CORS allows all origins (DEBUG mode)")
else:
    logger.info("cors_restricted_mode", allowed_origins=cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only allow necessary methods
    allow_headers=["Content-Type", "X-API-Key"],
    max_age=600,
)

# Monitoring middleware
if settings.ENABLE_METRICS:
    app.add_middleware(MonitoringMiddleware)


# Import routers
from api.routes import synthesis, templates as template_routes, monitoring

app.include_router(synthesis.router, prefix="/api/v1", tags=["synthesis"])
app.include_router(template_routes.router, prefix="/api/v1", tags=["templates"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "dashboard": "/api/v1/monitoring/dashboard",
        "metrics": "/api/v1/monitoring/metrics",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        cache_manager.redis_client.ping()

        return {
            "status": "healthy",
            "redis": "connected",
            "templates": len(template_manager.templates),
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/api/v1/stats")
async def get_system_stats():
    """Get comprehensive system statistics"""
    try:
        cache_stats = cache_manager.get_stats()
        pipeline_stats = matching_pipeline.get_stats()
        template_stats = template_manager.get_stats()

        return {
            "cache": cache_stats,
            "matching_pipeline": pipeline_stats,
            "templates": template_stats,
            "cost_savings": {
                "target_hit_rate": settings.TARGET_CACHE_HIT_RATE,
                "target_cost_reduction": settings.TARGET_COST_REDUCTION,
                "actual_hit_rate": cache_stats.get("cache_hit_rate", 0),
                "estimated_cost_reduction": cache_stats.get("cache_hit_rate", 0)
                * 0.9,  # Simplified estimate
            },
        }
    except Exception as e:
        logger.error("stats_retrieval_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")


@app.post("/api/v1/cache/clear")
@limiter.limit(LIMITS["admin"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def clear_cache(
    request: Request,
    api_key: str = Depends(verify_api_key) if settings.API_REQUIRE_AUTH else None
):
    """
    Clear entire cache (admin operation)

    Requires:
    - API key authentication (X-API-Key header)
    - Rate limited to 5 requests per hour
    """
    try:
        # Log admin operation
        if settings.ENABLE_AUDIT_LOG:
            await log_admin_operation(
                operation="cache_clear",
                api_key=api_key or "unauthenticated",
                client_ip=request.client.host if request.client else "unknown",
                details={"cache_stats_before": cache_manager.get_stats()}
            )

        cache_manager.clear()

        logger.warning(
            "cache_cleared_via_api",
            api_key=api_key.split(':')[0] if api_key and ':' in api_key else api_key,
            client_ip=request.client.host if request.client else "unknown"
        )

        return {"status": "success", "message": "Cache cleared"}
    except Exception as e:
        logger.error("cache_clear_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@app.post("/api/v1/admin/api-keys/create")
@limiter.limit(LIMITS["admin"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def create_api_key(
    request: Request,
    name: str,
    api_key: str = Depends(verify_api_key) if settings.API_REQUIRE_AUTH else None
):
    """
    Create a new API key (admin operation)

    Requires existing API key for authentication.
    Use this to create additional API keys for services or users.
    """
    try:
        # Log admin operation
        if settings.ENABLE_AUDIT_LOG:
            await log_admin_operation(
                operation="api_key_create",
                api_key=api_key or "unauthenticated",
                client_ip=request.client.host if request.client else "unknown",
                details={"new_key_name": name}
            )

        public_key, full_key = APIKeyManager.create_api_key(name)

        logger.info(
            "api_key_created",
            public_key=public_key,
            created_by=api_key.split(':')[0] if api_key and ':' in api_key else api_key
        )

        return {
            "status": "success",
            "public_key": public_key,
            "api_key": full_key,
            "warning": "Save this API key securely. It will not be shown again."
        }
    except Exception as e:
        logger.error("api_key_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create API key")


@app.get("/api/v1/admin/api-keys/list")
@limiter.limit(LIMITS["admin"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def list_api_keys(
    request: Request,
    api_key: str = Depends(verify_api_key) if settings.API_REQUIRE_AUTH else None
):
    """List all API keys (public identifiers only)"""
    try:
        keys = APIKeyManager.list_api_keys()

        return {
            "status": "success",
            "api_keys": keys,
            "count": len(keys)
        }
    except Exception as e:
        logger.error("api_key_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@app.delete("/api/v1/admin/api-keys/{public_key}")
@limiter.limit(LIMITS["admin"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def revoke_api_key(
    request: Request,
    public_key: str,
    api_key: str = Depends(verify_api_key) if settings.API_REQUIRE_AUTH else None
):
    """Revoke an API key"""
    try:
        # Log admin operation
        if settings.ENABLE_AUDIT_LOG:
            await log_admin_operation(
                operation="api_key_revoke",
                api_key=api_key or "unauthenticated",
                client_ip=request.client.host if request.client else "unknown",
                details={"revoked_key": public_key}
            )

        success = APIKeyManager.revoke_api_key(public_key)

        if success:
            return {"status": "success", "message": f"API key {public_key} revoked"}
        else:
            raise HTTPException(status_code=404, detail="API key not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_key_revocation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@app.get("/api/v1/admin/audit-log")
@limiter.limit(LIMITS["admin"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def get_audit_log(
    request: Request,
    limit: int = 100,
    event_filter: str = None,
    api_key: str = Depends(verify_api_key) if settings.API_REQUIRE_AUTH else None
):
    """Get audit log entries (admin only)"""
    try:
        entries = await AuditLog.get_audit_log(limit=limit, event_filter=event_filter)
        stats = await AuditLog.get_audit_stats()

        return {
            "status": "success",
            "entries": entries,
            "stats": stats
        }
    except Exception as e:
        logger.error("audit_log_retrieval_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve audit log")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
