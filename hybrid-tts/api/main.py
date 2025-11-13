"""
Main FastAPI application for Hybrid TTS Cost Optimizer
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from contextlib import asynccontextmanager

from config import settings
from cache.manager import cache_manager
from matching.pipeline import matching_pipeline
from templates.loader import template_manager

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

    yield

    # Shutdown
    logger.info("shutting_down_hybrid_tts_api")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Hybrid TTS Cost Optimizer - 70-90% cost reduction through intelligent caching",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Import routers
from api.routes import synthesis, templates as template_routes

app.include_router(synthesis.router, prefix="/api/v1", tags=["synthesis"])
app.include_router(template_routes.router, prefix="/api/v1", tags=["templates"])


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
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
async def clear_cache():
    """Clear entire cache (admin operation)"""
    try:
        cache_manager.clear()
        logger.warning("cache_cleared_via_api")
        return {"status": "success", "message": "Cache cleared"}
    except Exception as e:
        logger.error("cache_clear_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to clear cache")


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
