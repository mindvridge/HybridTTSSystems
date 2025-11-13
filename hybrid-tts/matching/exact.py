"""
Exact matching using hash-based lookup - O(1) time complexity
"""
import hashlib
from typing import Optional, Dict
import structlog

logger = structlog.get_logger()


class ExactMatcher:
    """
    Fast exact string matching using hash table
    Provides O(1) lookup for perfect matches
    """

    def __init__(self):
        self.phrase_cache: Dict[str, str] = {}
        logger.info("exact_matcher_initialized")

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent matching"""
        # Lowercase and strip whitespace
        normalized = text.lower().strip()
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def _generate_hash(self, text: str) -> str:
        """Generate hash for text"""
        normalized = self._normalize_text(text)
        return hashlib.md5(normalized.encode()).hexdigest()

    def add_phrase(self, phrase: str, identifier: str = None):
        """
        Add phrase to exact match index
        identifier: optional identifier to return on match (defaults to phrase)
        """
        hash_key = self._generate_hash(phrase)
        self.phrase_cache[hash_key] = identifier or phrase
        logger.debug("phrase_added", phrase=phrase[:50], hash=hash_key[:8])

    def match(self, query: str) -> Optional[str]:
        """
        Check for exact match
        Returns identifier if match found, None otherwise
        """
        hash_key = self._generate_hash(query)

        if hash_key in self.phrase_cache:
            result = self.phrase_cache[hash_key]
            logger.debug("exact_match_found", query=query[:50])
            return result

        logger.debug("exact_match_not_found", query=query[:50])
        return None

    def bulk_add(self, phrases: list[str]):
        """Add multiple phrases at once"""
        for phrase in phrases:
            self.add_phrase(phrase)
        logger.info("bulk_phrases_added", count=len(phrases))

    def get_stats(self) -> Dict:
        """Get matcher statistics"""
        return {
            "total_phrases": len(self.phrase_cache),
            "type": "exact",
        }
