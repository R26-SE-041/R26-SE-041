"""
Grounding Service — Verifies that generated content is grounded
in the uploaded source material using cosine similarity.

This is a KEY RESEARCH METRIC for the FYP paper.
"""
import os
import logging
import numpy as np
from typing import List
from dotenv import load_dotenv
from app.services.llm_service import EmbeddingService

load_dotenv()
logger = logging.getLogger(__name__)

GROUNDING_THRESHOLD = float(os.getenv("GROUNDING_THRESHOLD", "0.55"))


class GroundingService:
    """
    Computes grounding scores between generated content
    and source document chunks.
    
    Grounding Score = max cosine similarity between generated text
                      embedding and top source chunk embeddings.
    
    Score interpretation:
      > 0.75 : Strongly grounded
      0.55-0.75 : Moderately grounded
      < 0.55 : Weakly grounded (flag for review)
    """

    def __init__(self):
        self.embed = EmbeddingService()
        self.threshold = GROUNDING_THRESHOLD

    def score(
        self,
        generated_text: str,
        source_chunks: List[str]
    ) -> float:
        """
        Compute grounding score.
        
        Args:
            generated_text: The question/hint/explanation to verify
            source_chunks:  List of source text chunks to compare against
        
        Returns:
            Float 0.0-1.0. Higher = more grounded.
        """
        if not source_chunks or not generated_text.strip():
            return 0.0

        # Embed generated text
        gen_embedding = np.array(self.embed.get_query_embedding(generated_text))

        # Embed source chunks and compute similarities
        similarities = []
        for chunk in source_chunks:
            if not chunk.strip():
                continue
            chunk_embedding = np.array(self.embed.get_embedding(chunk))
            sim = self._cosine_similarity(gen_embedding, chunk_embedding)
            similarities.append(sim)

        if not similarities:
            return 0.0

        max_sim = float(max(similarities))
        logger.debug(f"Grounding score: {max_sim:.3f} (threshold={self.threshold})")
        return round(max_sim, 4)

    def is_grounded(self, generated_text: str, source_chunks: List[str]) -> bool:
        """Returns True if grounding score >= threshold."""
        return self.score(generated_text, source_chunks) >= self.threshold

    def score_batch(
        self,
        generated_texts: List[str],
        source_chunks: List[str]
    ) -> List[float]:
        """Compute grounding scores for multiple texts."""
        return [self.score(text, source_chunks) for text in generated_texts]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
