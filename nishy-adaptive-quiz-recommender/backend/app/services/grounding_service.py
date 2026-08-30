"""
Grounding Service — Verifies that generated content is grounded
in the uploaded source material using cosine similarity.

This is a KEY RESEARCH METRIC for the FYP paper.
"""
import json
import os
import re
import logging
import numpy as np
from typing import List, Dict, Any
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

    def validate_question(
        self,
        llm: Any,
        question: Dict,
        source_chunks: List[Dict],
    ) -> Dict:
        """Fail-closed validation of the answer and explanation against source text."""
        if not source_chunks:
            return self._failed_validation("no_source_context")

        options = question.get("options") or {}
        answer_key = str(question.get("correct_answer", "")).strip()
        answer_text = str(options.get(answer_key, question.get("correct_answer", ""))).strip()
        claim = "\n".join(
            part for part in (
                str(question.get("question", "")).strip(),
                answer_text,
                str(question.get("model_answer", "")).strip(),
            ) if part
        )
        score = self.score(claim, [str(chunk.get("text", "")) for chunk in source_chunks])
        if score < self.threshold:
            result = self._failed_validation("semantic_grounding_below_threshold")
            result["grounding_score"] = score
            return result

        labelled_context = "\n\n".join(
            "[CHUNK {chunk_id} | SOURCE {source} | PAGE {page}]\n{text}".format(
                chunk_id=chunk.get("chunk_id", ""),
                source=chunk.get("source", ""),
                page=chunk.get("page", 0),
                text=chunk.get("text", ""),
            )
            for chunk in source_chunks
        )
        prompt = f"""You are a strict question-quality auditor for Sri Lankan G.C.E. A/L Biology.
Use the labelled PDF excerpts to limit the question to the uploaded source. Apply only standard
Sri Lankan G.C.E. A/L Biology knowledge when judging whether each option is biologically true.
Do not repair, reinterpret, or silently change an ambiguous candidate.

SOURCE EXCERPTS:
{labelled_context}

CANDIDATE QUESTION JSON:
{json.dumps(question, ensure_ascii=False)}

Return ONLY JSON with exactly these fields:
{{"is_biology":true,"question_supported":true,"correct_answer_supported":true,"explanation_supported":true,"exactly_one_correct":true,"distractors_contextual":true,"has_unsupported_claims":false,"evidence_chunk_id":"exact chunk id","evidence_quote":"an exact continuous quote copied from that chunk","reason":"short reason"}}

Set every support field conservatively. For MCQs, exactly_one_correct is true only if one and only
one of the five choices is defensible at A/L Biology level. Reject combination/direct-option
transformations when two choices can both be true. The evidence quote must show that the tested
concept and choices came from the PDF; the correctness judgment must still be biologically sound.
If the candidate is weak, ambiguous, irrelevant, non-Biology, or insufficient, return false."""
        try:
            audit = llm.call_json(prompt)
        except Exception as exc:
            logger.warning(
                "Grounding audit LLM call failed (%s); rejecting candidate (score=%.3f)",
                exc,
                score,
            )
            result = self._failed_validation("grounding_audit_unavailable")
            result["grounding_score"] = score
            return result

        required = [
            "is_biology",
            "question_supported",
            "correct_answer_supported",
            "explanation_supported",
        ]
        if options:
            required.extend(("exactly_one_correct", "distractors_contextual"))
        passed = all(audit.get(field) is True for field in required)
        passed = passed and audit.get("has_unsupported_claims") is False

        chunk_id = str(audit.get("evidence_chunk_id", "")).strip()
        evidence_quote = str(audit.get("evidence_quote", "")).strip()
        evidence_chunk = next(
            (chunk for chunk in source_chunks if str(chunk.get("chunk_id", "")) == chunk_id),
            None,
        )
        quote_is_exact = bool(
            evidence_chunk
            and self._is_exact_quote(evidence_quote, str(evidence_chunk.get("text", "")))
        )
        passed = passed and quote_is_exact
        reason = str(audit.get("reason", "validation_failed"))
        if not quote_is_exact:
            reason = "invalid_evidence_quote"

        return {
            "grounding_status": "grounded" if passed else "rejected",
            "grounding_score": score,
            "evidence_chunk_id": chunk_id if passed else "",
            "evidence_quote": evidence_quote if passed else "",
            "reason": reason,
        }

    @staticmethod
    def _is_exact_quote(quote: str, source: str) -> bool:
        if len(quote.split()) < 4:
            return False
        normalize = lambda value: re.sub(r"\s+", " ", value).strip().casefold()
        return normalize(quote) in normalize(source)

    @staticmethod
    def _failed_validation(reason: str) -> Dict:
        return {
            "grounding_status": "rejected",
            "grounding_score": 0.0,
            "evidence_chunk_id": "",
            "evidence_quote": "",
            "reason": reason,
        }

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
