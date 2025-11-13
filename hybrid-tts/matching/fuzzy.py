"""
Fuzzy matching using thefuzz library
Handles minor variations in text (typos, word order)
"""
from typing import Optional, List, Tuple
from thefuzz import fuzz
import structlog
from config import settings

logger = structlog.get_logger()


class FuzzyMatcher:
    """
    Fuzzy string matching using token-based similarity
    Handles word order variations and minor typos
    """

    def __init__(self, threshold: int = None):
        self.threshold = threshold or settings.FUZZY_MATCH_THRESHOLD
        self.phrase_library: List[str] = []
        logger.info("fuzzy_matcher_initialized", threshold=self.threshold)

    def add_phrase(self, phrase: str):
        """Add phrase to fuzzy match library"""
        if phrase not in self.phrase_library:
            self.phrase_library.append(phrase)
            logger.debug("fuzzy_phrase_added", phrase=phrase[:50])

    def match(self, query: str, top_k: int = 1) -> Optional[Tuple[str, int]]:
        """
        Find best fuzzy match for query
        Returns (matched_phrase, score) if score >= threshold, None otherwise

        Uses Token Sort Ratio which handles:
        - Word order variations: "Green Plantain Large" vs "Large Plantain Green"
        - Case differences
        - Extra whitespace
        """
        if not self.phrase_library:
            logger.debug("fuzzy_library_empty")
            return None

        # Calculate scores for all phrases
        scores = []
        for phrase in self.phrase_library:
            # Token Sort Ratio: sorts tokens alphabetically before comparing
            score = fuzz.token_sort_ratio(query.lower(), phrase.lower())
            scores.append((phrase, score))

        # Sort by score (highest first)
        scores.sort(key=lambda x: x[1], reverse=True)

        # Get best match
        best_match, best_score = scores[0]

        if best_score >= self.threshold:
            logger.debug(
                "fuzzy_match_found",
                query=query[:50],
                match=best_match[:50],
                score=best_score,
            )
            return (best_match, best_score)

        logger.debug(
            "fuzzy_match_below_threshold",
            query=query[:50],
            best_score=best_score,
            threshold=self.threshold,
        )
        return None

    def match_multiple(self, query: str, top_k: int = 5) -> List[Tuple[str, int]]:
        """
        Return top-k fuzzy matches above threshold
        Useful for debugging and showing alternatives
        """
        if not self.phrase_library:
            return []

        scores = [
            (phrase, fuzz.token_sort_ratio(query.lower(), phrase.lower()))
            for phrase in self.phrase_library
        ]

        # Filter by threshold and sort
        matches = [
            (phrase, score) for phrase, score in scores if score >= self.threshold
        ]
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches[:top_k]

    def bulk_add(self, phrases: List[str]):
        """Add multiple phrases at once"""
        for phrase in phrases:
            self.add_phrase(phrase)
        logger.info("fuzzy_bulk_added", count=len(phrases))

    def get_stats(self) -> dict:
        """Get matcher statistics"""
        return {
            "total_phrases": len(self.phrase_library),
            "threshold": self.threshold,
            "type": "fuzzy",
        }
