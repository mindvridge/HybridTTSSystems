"""
Template management endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import structlog

from templates.loader import template_manager

logger = structlog.get_logger()

router = APIRouter()


class TemplateInfo(BaseModel):
    """Template information model"""

    template_id: str
    pattern: str
    slots: List[str]
    category: str
    description: str
    pre_recorded: bool


class TemplateRenderRequest(BaseModel):
    """Request model for template rendering"""

    template_id: str
    slot_values: Dict[str, Any]


@router.get("/templates", response_model=List[TemplateInfo])
async def list_templates(category: Optional[str] = None):
    """
    List all available templates
    Optionally filter by category
    """
    try:
        if category:
            templates = template_manager.get_templates_by_category(category)
        else:
            templates = list(template_manager.templates.values())

        return [
            TemplateInfo(
                template_id=t.template_id,
                pattern=t.pattern,
                slots=t.slots,
                category=t.category,
                description=t.description,
                pre_recorded=t.pre_recorded,
            )
            for t in templates
        ]

    except Exception as e:
        logger.error("list_templates_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list templates")


@router.get("/templates/{template_id}", response_model=TemplateInfo)
async def get_template(template_id: str):
    """Get specific template by ID"""
    template = template_manager.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=404, detail=f"Template '{template_id}' not found"
        )

    return TemplateInfo(
        template_id=template.template_id,
        pattern=template.pattern,
        slots=template.slots,
        category=template.category,
        description=template.description,
        pre_recorded=template.pre_recorded,
    )


@router.post("/templates/render")
async def render_template(request: TemplateRenderRequest):
    """
    Render template with slot values
    Returns rendered text without synthesis
    """
    try:
        rendered_text = template_manager.render_template(
            request.template_id, **request.slot_values
        )

        if not rendered_text:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{request.template_id}' not found or invalid slots",
            )

        return {"template_id": request.template_id, "rendered_text": rendered_text}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("template_render_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Template rendering failed")


@router.get("/templates/categories/list")
async def list_categories():
    """List all template categories"""
    return {
        "categories": list(template_manager.categories.keys()),
        "counts": {
            cat: len(ids) for cat, ids in template_manager.categories.items()
        },
    }


@router.get("/templates/stats")
async def get_template_stats():
    """Get template library statistics"""
    return template_manager.get_stats()


@router.get("/templates/static-phrases")
async def get_static_phrases():
    """
    Get all static phrases that can be pre-recorded
    Useful for cache warm-up
    """
    static_phrases = template_manager.get_all_static_phrases()

    return {
        "count": len(static_phrases),
        "phrases": static_phrases,
    }
