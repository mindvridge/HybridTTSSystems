"""
Text-to-Speech synthesis endpoints with hybrid caching
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
import structlog

from cache.manager import cache_manager
from matching.pipeline import matching_pipeline
from tts.provider import tts_provider
from tts.audio_processor import audio_processor
from templates.loader import template_manager
from monitoring import metrics_collector
from api.routes.monitoring import (
    synthesis_requests_total,
    synthesis_latency_seconds,
    audio_bytes_total,
)
from config import settings
from api.rate_limit import limiter, LIMITS

logger = structlog.get_logger()

router = APIRouter()


class SynthesisRequest(BaseModel):
    """Request model for TTS synthesis with security limits"""

    text: str = Field(
        ...,
        description="Text to synthesize",
        min_length=1,
        max_length=settings.MAX_TEXT_LENGTH
    )
    voice: Optional[str] = Field(None, description="Voice name/ID", max_length=100)
    use_cache: bool = Field(True, description="Whether to use cache")
    enable_matching: bool = Field(
        True, description="Enable fuzzy/semantic matching"
    )
    template_id: Optional[str] = Field(
        None, description="Template ID if using template", max_length=100
    )
    slot_values: Optional[Dict[str, Any]] = Field(
        None, description="Slot values for template"
    )

    @validator('text')
    def validate_text_length(cls, v):
        """Validate text doesn't exceed limits"""
        if len(v.strip()) == 0:
            raise ValueError("Text cannot be empty")
        if len(v) > settings.MAX_TEXT_LENGTH:
            raise ValueError(f"Text cannot exceed {settings.MAX_TEXT_LENGTH} characters")
        return v.strip()


class SynthesisResponse(BaseModel):
    """Response model for TTS synthesis"""

    success: bool
    method: str  # 'cache_hit', 'fuzzy_match', 'semantic_match', 'tts_synthesis'
    latency_ms: float
    audio_size: int
    matched_phrase: Optional[str] = None
    confidence_score: Optional[float] = None


@router.post("/synthesize", response_model=SynthesisResponse)
@limiter.limit(LIMITS["synthesis"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def synthesize_speech(http_request: Request, request: SynthesisRequest):
    """
    Main synthesis endpoint with hybrid matching pipeline

    Security:
    - Rate limited to 10 requests per minute per IP
    - Maximum text length: 5000 characters

    Process:
    1. Try exact cache hit
    2. Try fuzzy matching
    3. Try semantic matching
    4. Fallback to TTS synthesis and cache result
    """
    import time

    start_time = time.time()

    try:
        # If template is specified, render it first
        if request.template_id:
            rendered_text = template_manager.render_template(
                request.template_id, **(request.slot_values or {})
            )
            if not rendered_text:
                raise HTTPException(
                    status_code=400,
                    detail=f"Template {request.template_id} not found or invalid slots",
                )
            text_to_synthesize = rendered_text
        else:
            text_to_synthesize = request.text

        # Step 1: Check cache
        if request.use_cache:
            cached_audio = cache_manager.get(
                text_to_synthesize, voice=request.voice or ""
            )
            if cached_audio:
                latency = (time.time() - start_time) * 1000

                # Record metrics
                metrics_collector.record_synthesis(
                    method="exact",
                    latency_ms=latency,
                    text_length=len(text_to_synthesize),
                    audio_size=len(cached_audio),
                    confidence_score=1.0,
                )

                # Update Prometheus metrics
                synthesis_requests_total.labels(method="exact", status="success").inc()
                synthesis_latency_seconds.labels(method="exact").observe(latency / 1000)
                audio_bytes_total.labels(method="exact").inc(len(cached_audio))

                logger.info(
                    "synthesis_cache_hit",
                    text=text_to_synthesize[:50],
                    latency_ms=latency,
                )
                return Response(
                    content=cached_audio,
                    media_type="audio/ogg",
                    headers={
                        "X-Cache-Status": "HIT",
                        "X-Method": "exact_match",
                        "X-Latency-Ms": str(round(latency, 2)),
                    },
                )

        # Step 2: Try matching pipeline
        if request.enable_matching:
            match_result = matching_pipeline.match(text_to_synthesize)

            if match_result.matched:
                # Get cached audio for matched phrase
                matched_audio = cache_manager.get(
                    match_result.matched_phrase, voice=request.voice or ""
                )

                if matched_audio:
                    latency = (time.time() - start_time) * 1000

                    # Record metrics
                    metrics_collector.record_synthesis(
                        method=match_result.method,
                        latency_ms=latency,
                        text_length=len(text_to_synthesize),
                        audio_size=len(matched_audio),
                        confidence_score=match_result.confidence_score,
                        matched_phrase=match_result.matched_phrase,
                    )

                    # Update Prometheus metrics
                    synthesis_requests_total.labels(
                        method=match_result.method, status="success"
                    ).inc()
                    synthesis_latency_seconds.labels(method=match_result.method).observe(
                        latency / 1000
                    )
                    audio_bytes_total.labels(method=match_result.method).inc(
                        len(matched_audio)
                    )

                    logger.info(
                        "synthesis_matched",
                        method=match_result.method,
                        query=text_to_synthesize[:50],
                        matched=match_result.matched_phrase[:50],
                        latency_ms=latency,
                    )
                    return Response(
                        content=matched_audio,
                        media_type="audio/ogg",
                        headers={
                            "X-Cache-Status": "HIT",
                            "X-Method": match_result.method,
                            "X-Matched-Phrase": match_result.matched_phrase[:100],
                            "X-Confidence": str(
                                round(match_result.confidence_score, 4)
                            ),
                            "X-Latency-Ms": str(round(latency, 2)),
                        },
                    )

        # Step 3: Fallback to TTS synthesis
        logger.info("synthesis_fallback_to_tts", text=text_to_synthesize[:50])

        audio_data = await tts_provider.synthesize(
            text_to_synthesize, voice=request.voice
        )

        # Cache the result
        if request.use_cache:
            cache_manager.set(
                text_to_synthesize, audio_data, voice=request.voice or ""
            )

            # Also add to matching pipeline for future queries
            matching_pipeline.add_phrase(text_to_synthesize)

        latency = (time.time() - start_time) * 1000

        # Record metrics
        metrics_collector.record_synthesis(
            method="tts_synthesis",
            latency_ms=latency,
            text_length=len(text_to_synthesize),
            audio_size=len(audio_data),
            confidence_score=0.0,
        )

        # Update Prometheus metrics
        synthesis_requests_total.labels(method="tts_synthesis", status="success").inc()
        synthesis_latency_seconds.labels(method="tts_synthesis").observe(latency / 1000)
        audio_bytes_total.labels(method="tts_synthesis").inc(len(audio_data))

        logger.info(
            "synthesis_tts_complete",
            text=text_to_synthesize[:50],
            audio_size=len(audio_data),
            latency_ms=latency,
        )

        return Response(
            content=audio_data,
            media_type="audio/ogg",
            headers={
                "X-Cache-Status": "MISS",
                "X-Method": "tts_synthesis",
                "X-Latency-Ms": str(round(latency, 2)),
            },
        )

    except Exception as e:
        # Record failed request
        synthesis_requests_total.labels(method="unknown", status="error").inc()

        logger.error("synthesis_failed", error=str(e), text=request.text[:50])
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.post("/synthesize/batch")
@limiter.limit(LIMITS["batch"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def synthesize_batch(http_request: Request, texts: list[str], voice: Optional[str] = None):
    """
    Batch synthesis for multiple texts

    Security:
    - Rate limited to 5 requests per minute per IP
    - Maximum batch size: 100 items
    - Each text limited to 5000 characters

    Returns array of audio data with metadata
    """
    # Validate batch size
    if len(texts) > settings.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum of {settings.MAX_BATCH_SIZE} items"
        )

    # Validate each text length
    for i, text in enumerate(texts):
        if len(text) > settings.MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Text at index {i} exceeds maximum length of {settings.MAX_TEXT_LENGTH} characters"
            )

    results = []

    for text in texts:
        try:
            request = SynthesisRequest(text=text, voice=voice)
            # Note: This is a simplified version
            # In production, you'd want to optimize this
            result = await synthesize_speech(http_request, request)
            results.append(
                {"text": text, "success": True, "audio_available": True}
            )
        except Exception as e:
            logger.error("batch_synthesis_item_failed", text=text[:50], error=str(e))
            results.append(
                {"text": text, "success": False, "error": str(e)}
            )

    return {"total": len(texts), "results": results}


@router.post("/synthesize/template")
@limiter.limit(LIMITS["synthesis"]) if settings.ENABLE_RATE_LIMITING else lambda x: x
async def synthesize_from_template(
    http_request: Request,
    template_id: str,
    slot_values: Dict[str, Any],
    voice: Optional[str] = None
):
    """
    Synthesize speech from template

    Security:
    - Rate limited to 10 requests per minute per IP
    - Template output limited to 5000 characters

    This is the recommended way for structured responses
    """
    try:
        # Render template
        rendered_text = template_manager.render_template(template_id, **slot_values)
        if not rendered_text:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{template_id}' not found or invalid slots",
            )

        # Synthesize
        request = SynthesisRequest(
            text=rendered_text,
            voice=voice,
            template_id=template_id,
            slot_values=slot_values,
        )

        return await synthesize_speech(http_request, request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "template_synthesis_failed",
            template_id=template_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Template synthesis failed: {str(e)}"
        )


@router.get("/synthesis/stats")
async def get_synthesis_stats():
    """Get synthesis and matching statistics"""
    pipeline_stats = matching_pipeline.get_stats()
    cache_stats = cache_manager.get_stats()

    return {
        "pipeline": pipeline_stats,
        "cache": cache_stats,
    }
