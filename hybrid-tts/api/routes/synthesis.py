"""
Text-to-Speech synthesis endpoints with hybrid caching
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import structlog

from cache.manager import cache_manager
from matching.pipeline import matching_pipeline
from tts.provider import tts_provider
from tts.audio_processor import audio_processor
from templates.loader import template_manager

logger = structlog.get_logger()

router = APIRouter()


class SynthesisRequest(BaseModel):
    """Request model for TTS synthesis"""

    text: str = Field(..., description="Text to synthesize", min_length=1)
    voice: Optional[str] = Field(None, description="Voice name/ID")
    use_cache: bool = Field(True, description="Whether to use cache")
    enable_matching: bool = Field(
        True, description="Enable fuzzy/semantic matching"
    )
    template_id: Optional[str] = Field(
        None, description="Template ID if using template"
    )
    slot_values: Optional[Dict[str, Any]] = Field(
        None, description="Slot values for template"
    )


class SynthesisResponse(BaseModel):
    """Response model for TTS synthesis"""

    success: bool
    method: str  # 'cache_hit', 'fuzzy_match', 'semantic_match', 'tts_synthesis'
    latency_ms: float
    audio_size: int
    matched_phrase: Optional[str] = None
    confidence_score: Optional[float] = None


@router.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_speech(request: SynthesisRequest):
    """
    Main synthesis endpoint with hybrid matching pipeline

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
        logger.error("synthesis_failed", error=str(e), text=request.text[:50])
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.post("/synthesize/batch")
async def synthesize_batch(texts: list[str], voice: Optional[str] = None):
    """
    Batch synthesis for multiple texts
    Returns array of audio data with metadata
    """
    results = []

    for text in texts:
        try:
            request = SynthesisRequest(text=text, voice=voice)
            # Note: This is a simplified version
            # In production, you'd want to optimize this
            result = await synthesize_speech(request)
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
async def synthesize_from_template(
    template_id: str, slot_values: Dict[str, Any], voice: Optional[str] = None
):
    """
    Synthesize speech from template
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

        return await synthesize_speech(request)

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
