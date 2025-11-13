"""
Unified matching pipeline with weighted scoring
Cascades through: Exact -> Fuzzy -> Semantic -> TTS Fallback
"""
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
import structlog
from config import settings
from matching.exact import ExactMatcher
from matching.fuzzy import FuzzyMatcher
from matching.semantic import SemanticMatcher

logger = structlog.get_logger()


@dataclass
class MatchResult:
    """Result from matching pipeline"""

    matched: bool
    method: str  # 'exact', 'fuzzy', 'semantic', 'fallback'
    matched_phrase: Optional[str] = None
    confidence_score: float = 0.0
    latency_ms: float = 0.0
    details: Dict[str, Any] = None


class MatchingPipeline:
    """
    Multi-stage matching pipeline with timeout controls
    Tries methods in order of speed: exact -> fuzzy -> semantic -> fallback
    """

    def __init__(self):
        self.exact_matcher = ExactMatcher()
        self.fuzzy_matcher = FuzzyMatcher()
        self.semantic_matcher = SemanticMatcher()

        # Statistics
        self.stats = {
            "total_matches": 0,
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "semantic_matches": 0,
            "fallbacks": 0,
        }

        logger.info("matching_pipeline_initialized")

    def add_phrase(self, phrase: str):
        """Add phrase to all matchers"""
        self.exact_matcher.add_phrase(phrase)
        self.fuzzy_matcher.add_phrase(phrase)
        self.semantic_matcher.add_phrase(phrase)

    def bulk_add_phrases(self, phrases: list[str]):
        """Add multiple phrases to all matchers (more efficient)"""
        self.exact_matcher.bulk_add(phrases)
        self.fuzzy_matcher.bulk_add(phrases)
        self.semantic_matcher.bulk_add(phrases)
        logger.info("pipeline_phrases_added", count=len(phrases))

    def match(self, query: str, enable_fallback: bool = True) -> MatchResult:
        """
        Match query through pipeline stages
        Returns MatchResult with best match or fallback indicator
        """
        start_time = time.time()
        self.stats["total_matches"] += 1

        # Stage 1: Exact Match (1-5ms target)
        exact_result = self._try_exact_match(query)
        if exact_result.matched:
            exact_result.latency_ms = (time.time() - start_time) * 1000
            self.stats["exact_matches"] += 1
            return exact_result

        # Stage 2: Fuzzy Match (10-50ms target)
        fuzzy_result = self._try_fuzzy_match(query)
        if fuzzy_result.matched:
            fuzzy_result.latency_ms = (time.time() - start_time) * 1000
            self.stats["fuzzy_matches"] += 1
            return fuzzy_result

        # Stage 3: Semantic Match (50-100ms target)
        semantic_result = self._try_semantic_match(query)
        if semantic_result.matched:
            semantic_result.latency_ms = (time.time() - start_time) * 1000
            self.stats["semantic_matches"] += 1
            return semantic_result

        # Stage 4: Fallback to TTS
        if enable_fallback:
            self.stats["fallbacks"] += 1
            fallback_result = MatchResult(
                matched=False,
                method="fallback",
                latency_ms=(time.time() - start_time) * 1000,
                details={"reason": "no_match_found", "query": query},
            )
            logger.info("fallback_to_tts", query=query[:50])
            return fallback_result

        # No match and fallback disabled
        return MatchResult(
            matched=False,
            method="none",
            latency_ms=(time.time() - start_time) * 1000,
        )

    def _try_exact_match(self, query: str) -> MatchResult:
        """Try exact matching with timeout"""
        try:
            start = time.time()
            result = self.exact_matcher.match(query)
            elapsed_ms = (time.time() - start) * 1000

            if elapsed_ms > settings.EXACT_MATCH_TIMEOUT_MS:
                logger.warning("exact_match_timeout", elapsed_ms=elapsed_ms)

            if result:
                return MatchResult(
                    matched=True,
                    method="exact",
                    matched_phrase=result,
                    confidence_score=1.0,
                    latency_ms=elapsed_ms,
                )

        except Exception as e:
            logger.error("exact_match_error", error=str(e))

        return MatchResult(matched=False, method="exact")

    def _try_fuzzy_match(self, query: str) -> MatchResult:
        """Try fuzzy matching with timeout"""
        try:
            start = time.time()
            result = self.fuzzy_matcher.match(query)
            elapsed_ms = (time.time() - start) * 1000

            if elapsed_ms > settings.FUZZY_MATCH_TIMEOUT_MS:
                logger.warning("fuzzy_match_timeout", elapsed_ms=elapsed_ms)

            if result:
                matched_phrase, score = result
                # Normalize score to 0-1 range
                normalized_score = score / 100.0

                return MatchResult(
                    matched=True,
                    method="fuzzy",
                    matched_phrase=matched_phrase,
                    confidence_score=normalized_score,
                    latency_ms=elapsed_ms,
                    details={"raw_score": score},
                )

        except Exception as e:
            logger.error("fuzzy_match_error", error=str(e))

        return MatchResult(matched=False, method="fuzzy")

    def _try_semantic_match(self, query: str) -> MatchResult:
        """Try semantic matching with timeout"""
        try:
            start = time.time()
            result = self.semantic_matcher.match(query)
            elapsed_ms = (time.time() - start) * 1000

            if elapsed_ms > settings.SEMANTIC_MATCH_TIMEOUT_MS:
                logger.warning("semantic_match_timeout", elapsed_ms=elapsed_ms)

            if result:
                matched_phrase, score = result

                return MatchResult(
                    matched=True,
                    method="semantic",
                    matched_phrase=matched_phrase,
                    confidence_score=score,
                    latency_ms=elapsed_ms,
                    details={"cosine_similarity": score},
                )

        except Exception as e:
            logger.error("semantic_match_error", error=str(e))

        return MatchResult(matched=False, method="semantic")

    def match_with_weighted_scoring(self, query: str) -> MatchResult:
        """
        Advanced matching with weighted score combination
        Uses formula: final_score = 0.5*exact + 0.3*fuzzy + 0.2*semantic
        """
        scores = {}

        # Try all matchers
        exact_match = self.exact_matcher.match(query)
        scores["exact"] = 1.0 if exact_match else 0.0

        fuzzy_result = self.fuzzy_matcher.match(query)
        scores["fuzzy"] = fuzzy_result[1] / 100.0 if fuzzy_result else 0.0

        semantic_result = self.semantic_matcher.match(query)
        scores["semantic"] = semantic_result[1] if semantic_result else 0.0

        # Calculate weighted final score
        final_score = (
            settings.WEIGHT_EXACT * scores["exact"]
            + settings.WEIGHT_FUZZY * scores["fuzzy"]
            + settings.WEIGHT_SEMANTIC * scores["semantic"]
        )

        # Determine best match
        if exact_match:
            matched_phrase = exact_match
            method = "exact"
        elif fuzzy_result:
            matched_phrase = fuzzy_result[0]
            method = "fuzzy"
        elif semantic_result:
            matched_phrase = semantic_result[0]
            method = "semantic"
        else:
            return MatchResult(matched=False, method="fallback")

        return MatchResult(
            matched=True,
            method=f"weighted_{method}",
            matched_phrase=matched_phrase,
            confidence_score=final_score,
            details={"component_scores": scores, "weights_used": True},
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        total = self.stats["total_matches"]
        if total == 0:
            return {**self.stats, "distribution": {}}

        distribution = {
            "exact_rate": round(self.stats["exact_matches"] / total, 4),
            "fuzzy_rate": round(self.stats["fuzzy_matches"] / total, 4),
            "semantic_rate": round(self.stats["semantic_matches"] / total, 4),
            "fallback_rate": round(self.stats["fallbacks"] / total, 4),
        }

        return {
            **self.stats,
            "distribution": distribution,
            "cache_hit_rate": round(
                1 - (self.stats["fallbacks"] / total), 4
            ),  # Important metric!
        }


# Global pipeline instance
matching_pipeline = MatchingPipeline()
