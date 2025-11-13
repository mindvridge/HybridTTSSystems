"""
Semantic matching using sentence embeddings
Handles paraphrases and semantically similar queries
"""
import numpy as np
from typing import Optional, List, Tuple
from sentence_transformers import SentenceTransformer
import structlog
from config import settings

logger = structlog.get_logger()


class SemanticMatcher:
    """
    Semantic similarity matching using sentence embeddings
    Handles paraphrases and meaning-based similarity
    """

    def __init__(self, threshold: float = None):
        self.threshold = threshold or settings.SEMANTIC_MATCH_THRESHOLD
        self.model = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
        self.phrase_library: List[str] = []
        self.embeddings: Optional[np.ndarray] = None

        logger.info(
            "semantic_matcher_initialized",
            model=settings.SENTENCE_TRANSFORMER_MODEL,
            threshold=self.threshold,
        )

    def add_phrase(self, phrase: str):
        """Add phrase to semantic library and recompute embeddings"""
        if phrase not in self.phrase_library:
            self.phrase_library.append(phrase)
            # Recompute embeddings
            self._update_embeddings()
            logger.debug("semantic_phrase_added", phrase=phrase[:50])

    def bulk_add(self, phrases: List[str]):
        """
        Add multiple phrases at once (more efficient than individual adds)
        Computes embeddings in batch
        """
        new_phrases = [p for p in phrases if p not in self.phrase_library]
        if new_phrases:
            self.phrase_library.extend(new_phrases)
            self._update_embeddings()
            logger.info("semantic_bulk_added", count=len(new_phrases))

    def _update_embeddings(self):
        """Compute embeddings for all phrases in library"""
        if not self.phrase_library:
            self.embeddings = None
            return

        logger.debug("computing_embeddings", phrase_count=len(self.phrase_library))
        self.embeddings = self.model.encode(
            self.phrase_library,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        logger.debug("embeddings_computed", shape=self.embeddings.shape)

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def match(self, query: str, top_k: int = 1) -> Optional[Tuple[str, float]]:
        """
        Find semantically similar phrase
        Returns (matched_phrase, similarity_score) if score >= threshold

        Similarity score is cosine similarity in range [0, 1]
        """
        if not self.phrase_library or self.embeddings is None:
            logger.debug("semantic_library_empty")
            return None

        # Encode query
        query_embedding = self.model.encode(
            [query], convert_to_numpy=True, show_progress_bar=False
        )[0]

        # Calculate cosine similarities with all phrases
        similarities = []
        for idx, phrase_embedding in enumerate(self.embeddings):
            similarity = self._cosine_similarity(query_embedding, phrase_embedding)
            similarities.append((self.phrase_library[idx], float(similarity)))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Get best match
        best_match, best_score = similarities[0]

        if best_score >= self.threshold:
            logger.debug(
                "semantic_match_found",
                query=query[:50],
                match=best_match[:50],
                score=round(best_score, 4),
            )
            return (best_match, best_score)

        logger.debug(
            "semantic_match_below_threshold",
            query=query[:50],
            best_score=round(best_score, 4),
            threshold=self.threshold,
        )
        return None

    def match_multiple(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Return top-k semantic matches above threshold
        Useful for debugging and showing alternatives
        """
        if not self.phrase_library or self.embeddings is None:
            return []

        # Encode query
        query_embedding = self.model.encode(
            [query], convert_to_numpy=True, show_progress_bar=False
        )[0]

        # Calculate similarities
        similarities = []
        for idx, phrase_embedding in enumerate(self.embeddings):
            similarity = self._cosine_similarity(query_embedding, phrase_embedding)
            if similarity >= self.threshold:
                similarities.append((self.phrase_library[idx], float(similarity)))

        # Sort and return top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def get_stats(self) -> dict:
        """Get matcher statistics"""
        return {
            "total_phrases": len(self.phrase_library),
            "threshold": self.threshold,
            "embedding_dim": settings.VECTOR_DIM,
            "model": settings.SENTENCE_TRANSFORMER_MODEL,
            "type": "semantic",
        }
