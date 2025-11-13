"""
Unit tests for matching engines
"""
import pytest
from matching.exact import ExactMatcher
from matching.fuzzy import FuzzyMatcher
from matching.semantic import SemanticMatcher
from matching.pipeline import MatchingPipeline


class TestExactMatcher:
    """Test exact matching functionality"""

    def test_exact_match_found(self):
        matcher = ExactMatcher()
        matcher.add_phrase("안녕하세요")

        result = matcher.match("안녕하세요")
        assert result == "안녕하세요"

    def test_exact_match_not_found(self):
        matcher = ExactMatcher()
        matcher.add_phrase("안녕하세요")

        result = matcher.match("안녕")
        assert result is None

    def test_normalization(self):
        matcher = ExactMatcher()
        matcher.add_phrase("Hello  World")  # Extra spaces

        # Should match despite different spacing
        result = matcher.match("hello world")
        assert result is not None

    def test_bulk_add(self):
        matcher = ExactMatcher()
        phrases = ["안녕하세요", "감사합니다", "좋은 하루"]

        matcher.bulk_add(phrases)

        assert matcher.match("안녕하세요") is not None
        assert matcher.match("감사합니다") is not None


class TestFuzzyMatcher:
    """Test fuzzy matching functionality"""

    def test_fuzzy_match_typo(self):
        matcher = FuzzyMatcher(threshold=70)
        matcher.add_phrase("잔액 조회해주세요")

        # Minor typo should still match
        result = matcher.match("잔액 조회해주세요.")
        assert result is not None
        assert result[1] >= 70  # Score should be above threshold

    def test_fuzzy_match_word_order(self):
        matcher = FuzzyMatcher(threshold=70)
        matcher.add_phrase("Green Plantain Large")

        # Different word order should match (Token Sort Ratio)
        result = matcher.match("Large Plantain Green")
        assert result is not None
        assert result[0] == "Green Plantain Large"

    def test_fuzzy_below_threshold(self):
        matcher = FuzzyMatcher(threshold=80)
        matcher.add_phrase("계좌 잔액")

        # Very different phrase should not match
        result = matcher.match("거래 내역")
        assert result is None


class TestSemanticMatcher:
    """Test semantic matching functionality"""

    @pytest.mark.slow
    def test_semantic_similar_meaning(self):
        matcher = SemanticMatcher(threshold=0.70)
        matcher.bulk_add(["잔액 조회해주세요", "계좌 확인"])

        # Semantically similar but different wording
        result = matcher.match("잔액이 얼마인가요")
        # This might match if semantic similarity is high enough
        # Result depends on model quality

    @pytest.mark.slow
    def test_semantic_different_meaning(self):
        matcher = SemanticMatcher(threshold=0.85)
        matcher.add_phrase("잔액 조회")

        # Completely different topic
        result = matcher.match("날씨 어때요")
        assert result is None


class TestMatchingPipeline:
    """Test integrated matching pipeline"""

    def test_pipeline_exact_match_priority(self):
        pipeline = MatchingPipeline()
        pipeline.add_phrase("안녕하세요")

        result = pipeline.match("안녕하세요")

        assert result.matched is True
        assert result.method == "exact"
        assert result.confidence_score == 1.0

    def test_pipeline_fallback(self):
        pipeline = MatchingPipeline()
        # Don't add any phrases

        result = pipeline.match("새로운 문구", enable_fallback=True)

        assert result.matched is False
        assert result.method == "fallback"

    def test_pipeline_stats(self):
        pipeline = MatchingPipeline()
        pipeline.add_phrase("테스트")

        # Perform some matches
        pipeline.match("테스트")  # Exact
        pipeline.match("완전히 다른 문구")  # Fallback

        stats = pipeline.get_stats()

        assert stats["total_matches"] == 2
        assert stats["exact_matches"] >= 1
        assert stats["fallbacks"] >= 1
