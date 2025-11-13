"""
Unit tests for template system
"""
import pytest
from templates.loader import Template, TemplateManager


class TestTemplate:
    """Test template functionality"""

    def test_template_fill(self):
        template = Template(
            template_id="test",
            pattern="{name}님의 잔액은 {balance}원입니다",
            slots=["name", "balance"],
        )

        result = template.fill(name="김철수", balance="1,000,000")
        assert result == "김철수님의 잔액은 1,000,000원입니다"

    def test_template_validate_slots(self):
        template = Template(
            template_id="test",
            pattern="{name}님 안녕하세요",
            slots=["name"],
        )

        # Valid slots
        assert template.validate_slots({"name": "김철수"}) is True

        # Missing slots
        assert template.validate_slots({}) is False

    def test_static_parts_extraction(self):
        template = Template(
            template_id="test",
            pattern="Hello {name}, your balance is {balance}",
            slots=["name", "balance"],
        )

        parts = template.static_parts
        assert len(parts) == 3
        assert "Hello " in parts
        assert ", your balance is " in parts


class TestTemplateManager:
    """Test template manager functionality"""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create template manager with test data"""
        # Create temporary template file
        template_file = tmp_path / "test_templates.yaml"
        template_file.write_text(
            """
templates:
  - id: greeting
    pattern: "안녕하세요"
    slots: []
    category: general
    description: "Greeting"
    pre_recorded: true

  - id: balance
    pattern: "{name}님의 잔액은 {amount}원입니다"
    slots:
      - name
      - amount
    category: banking
    description: "Balance inquiry"
    pre_recorded: false
"""
        )

        return TemplateManager(template_file=str(template_file))

    def test_load_templates(self, manager):
        assert len(manager.templates) == 2
        assert "greeting" in manager.templates
        assert "balance" in manager.templates

    def test_get_template(self, manager):
        template = manager.get_template("greeting")
        assert template is not None
        assert template.pattern == "안녕하세요"

    def test_render_template(self, manager):
        result = manager.render_template(
            "balance", name="김철수", amount="1,000,000"
        )
        assert result == "김철수님의 잔액은 1,000,000원입니다"

    def test_get_templates_by_category(self, manager):
        banking_templates = manager.get_templates_by_category("banking")
        assert len(banking_templates) == 1
        assert banking_templates[0].template_id == "balance"

    def test_get_static_phrases(self, manager):
        static_phrases = manager.get_all_static_phrases()
        assert "안녕하세요" in static_phrases
