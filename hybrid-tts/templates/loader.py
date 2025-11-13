"""
Template loader and manager for parametric response templates
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import structlog
from config import settings

logger = structlog.get_logger()


class Template:
    """
    Represents a parametric template with slots
    Example: "계좌번호 {account_number}의 잔액은 {balance}원입니다"
    """

    def __init__(
        self,
        template_id: str,
        pattern: str,
        slots: List[str],
        category: str = "general",
        description: str = "",
        pre_recorded: bool = False,
    ):
        self.template_id = template_id
        self.pattern = pattern
        self.slots = slots
        self.category = category
        self.description = description
        self.pre_recorded = pre_recorded

        # Extract static parts and slot positions
        self.static_parts = self._extract_static_parts()

    def _extract_static_parts(self) -> List[str]:
        """
        Extract static text parts from template
        E.g., "Your order {order_id} will arrive on {date}"
        -> ["Your order ", " will arrive on ", ""]
        """
        # Split by slot patterns
        parts = re.split(r"\{[^}]+\}", self.pattern)
        return parts

    def fill(self, **slot_values) -> str:
        """
        Fill template with slot values
        Returns rendered text
        """
        result = self.pattern
        for slot_name, slot_value in slot_values.items():
            placeholder = f"{{{slot_name}}}"
            result = result.replace(placeholder, str(slot_value))

        # Check for unfilled slots
        remaining_slots = re.findall(r"\{([^}]+)\}", result)
        if remaining_slots:
            logger.warning(
                "unfilled_slots",
                template_id=self.template_id,
                missing_slots=remaining_slots,
            )

        return result

    def validate_slots(self, slot_values: Dict[str, Any]) -> bool:
        """Check if all required slots are provided"""
        provided_slots = set(slot_values.keys())
        required_slots = set(self.slots)

        missing = required_slots - provided_slots
        if missing:
            logger.warning(
                "missing_required_slots",
                template_id=self.template_id,
                missing=list(missing),
            )
            return False

        return True

    def to_dict(self) -> Dict:
        """Convert template to dictionary"""
        return {
            "template_id": self.template_id,
            "pattern": self.pattern,
            "slots": self.slots,
            "category": self.category,
            "description": self.description,
            "pre_recorded": self.pre_recorded,
        }


class TemplateManager:
    """
    Manages template library loading and rendering
    """

    def __init__(self, template_file: str = None):
        self.template_file = Path(template_file or settings.TEMPLATE_FILE)
        self.templates: Dict[str, Template] = {}
        self.categories: Dict[str, List[str]] = {}

        # Load templates if file exists
        if self.template_file.exists():
            self.load_templates()
        else:
            logger.warning("template_file_not_found", path=str(self.template_file))

    def load_templates(self):
        """Load templates from YAML file"""
        try:
            with open(self.template_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "templates" not in data:
                logger.warning("no_templates_in_file")
                return

            # Parse templates
            for template_data in data["templates"]:
                template = Template(
                    template_id=template_data["id"],
                    pattern=template_data["pattern"],
                    slots=template_data.get("slots", []),
                    category=template_data.get("category", "general"),
                    description=template_data.get("description", ""),
                    pre_recorded=template_data.get("pre_recorded", False),
                )

                self.templates[template.template_id] = template

                # Index by category
                category = template.category
                if category not in self.categories:
                    self.categories[category] = []
                self.categories[category].append(template.template_id)

            logger.info(
                "templates_loaded",
                count=len(self.templates),
                categories=list(self.categories.keys()),
            )

        except Exception as e:
            logger.error("template_load_failed", error=str(e))
            raise

    def get_template(self, template_id: str) -> Optional[Template]:
        """Get template by ID"""
        return self.templates.get(template_id)

    def render_template(self, template_id: str, **slot_values) -> Optional[str]:
        """
        Render template with slot values
        Returns rendered text or None if template not found
        """
        template = self.get_template(template_id)
        if not template:
            logger.warning("template_not_found", template_id=template_id)
            return None

        if not template.validate_slots(slot_values):
            return None

        return template.fill(**slot_values)

    def get_templates_by_category(self, category: str) -> List[Template]:
        """Get all templates in a category"""
        template_ids = self.categories.get(category, [])
        return [self.templates[tid] for tid in template_ids]

    def get_all_static_phrases(self) -> List[str]:
        """
        Get all static (non-parametric) phrases for pre-recording
        Returns list of complete phrases that can be cached
        """
        static_phrases = []

        for template in self.templates.values():
            # If template has no slots, it's completely static
            if not template.slots:
                static_phrases.append(template.pattern)

            # Add static parts of parametric templates
            for part in template.static_parts:
                if part.strip():  # Non-empty static part
                    static_phrases.append(part.strip())

        return static_phrases

    def list_templates(self) -> List[Dict]:
        """Get list of all templates as dictionaries"""
        return [t.to_dict() for t in self.templates.values()]

    def get_stats(self) -> Dict:
        """Get template library statistics"""
        total = len(self.templates)
        pre_recorded = sum(1 for t in self.templates.values() if t.pre_recorded)
        parametric = sum(1 for t in self.templates.values() if t.slots)

        return {
            "total_templates": total,
            "pre_recorded_count": pre_recorded,
            "parametric_count": parametric,
            "static_count": total - parametric,
            "categories": {
                cat: len(ids) for cat, ids in self.categories.items()
            },
        }


# Global template manager instance
template_manager = TemplateManager()
