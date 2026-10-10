"""
Recommendation Agent — Identifies weak topics and returns:
1. LLM-generated concept notes (bullet points) for each weak topic
2. Specific, validated learning resource links scraped from the actual pages
   (GFG article, TutorialsPoint tutorial, YouTube video — NOT search pages)
"""
import os
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv
from app.graph.state import AssessmentState
from app.services.llm_service import LlmService
from app.services.rag_service import RagService
from app.services.url_validator import build_resources

load_dotenv()
logger = logging.getLogger(__name__)

WEAK_THRESHOLD = float(os.getenv("WEAK_TOPIC_THRESHOLD", "0.60"))

# Load resource map from JSON file (curated overrides for known topics)
_RESOURCE_MAP_PATH = Path(__file__).parent.parent / "data" / "resources" / "resource_map.json"


CONCEPT_NOTES_PROMPT = """You are a {subject} teacher. A student struggled with "{topic}".

Use the following material from their uploaded study notes:
{context}

Write a deep chapter-recall guide that rebuilds the student's understanding of "{topic}" using ONLY this material.

Format your response as exactly 7-10 bullet points. Each bullet point must:
- Start with a bold keyword (e.g. **Keyword**: explanation)
- Give a self-contained 2-4 sentence explanation, not a label or one-line answer
- Use {subject} terminology and exam-level depth
- Together cover: definition, structures/components, process or mechanism, relationships,
  comparisons, cause-effect, common misconceptions, and an exam application/decision rule
- Explicitly connect related ideas so the student can recall the surrounding chapter
- Include only claims supported by the supplied material

Do NOT include:
- Any intro/outro sentences
- Headers or section titles
- Numbered lists
- The phrase "the uploaded material" or "the document"

Return ONLY the bullet points, nothing else."""


def _extractive_recall_notes(chunks: list) -> list:
    """Build source-only recall notes when the model is unavailable."""
    notes = []
    seen = set()
    for chunk in chunks:
        text = " ".join(str(chunk.get("text", "")).split())
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = sentence.strip()
            key = sentence.casefold()
            if not (8 <= len(sentence.split()) <= 55) or key in seen:
                continue
            seen.add(key)
            heading = " ".join(sentence.split()[:3]).strip(" ,;:")
            notes.append(f"**{heading}**: {sentence}")
            if len(notes) >= 10:
                return notes
    return notes


def _load_resource_map() -> dict:
    try:
        with open(_RESOURCE_MAP_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load resource_map.json: {e}")
        return {}


def _curated_resources(topic: str, resource_map: dict) -> list:
    """
    Check if the topic has hand-curated resources in the resource_map.json.
    Returns a list of structured resource dicts, or [] if none found.
    These are preferred over scraped URLs since they are pre-verified.
    """
    topic_lower = topic.lower()
    matched_raw = []
    for key, resources in resource_map.items():
        if key.lower() in topic_lower or topic_lower in key.lower():
            matched_raw.extend(resources)

    structured = []
    for r in matched_raw[:3]:
        lang = r.get("language", "english").lower()
        label = {"english": "English", "tamil": "Tamil", "sinhala": "Sinhala"}.get(lang, "English")
        structured.append({
            "label":  label,
            "title":  r.get("title", topic),
            "url":    r.get("url", ""),
            "source": r.get("source", "GeeksforGeeks"),
        })
    return structured


def _generate_concept_notes(
    topic: str,
    rag: RagService,
    llm: LlmService,
    collection_id: str,
    subject: str = "Sri Lankan G.C.E. A/L Biology",
    source_chunks: list | None = None,
) -> list:
    """Generate bullet-point concept notes for a weak topic using RAG context."""
    try:
        chunks = list(source_chunks or []) or rag.retrieve(
            collection_id,
            f"{subject} {topic} definition structure process relationship",
            k=8,
        )
        context = "\n\n".join([c["text"] for c in chunks]) if chunks else ""
        if not context:
            return []

        prompt = CONCEPT_NOTES_PROMPT.format(subject=subject, topic=topic, context=context)
        raw = llm.call(prompt, max_new_tokens=700)

        # Parse bullet points — lines starting with - or •
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
        bullets = [l for l in lines if l.startswith("-") or l.startswith("•") or l.startswith("*")]

        # Fallback: if model didn't use bullet format, treat each sentence as a bullet
        if not bullets:
            bullets = [f"- {l}" for l in lines[:6] if len(l) > 15]

        # Clean up and return a complete recall set.
        cleaned = []
        for b in bullets[:10]:
            b = b.lstrip("-•* ").strip()
            if b:
                cleaned.append(b)
        if cleaned:
            return cleaned

        # Fail closed to extractive, source-only recall points instead of
        # introducing general-knowledge claims.
        return _extractive_recall_notes(chunks)

    except Exception as e:
        logger.error(f"[RecommendationAgent] Concept notes failed for '{topic}': {e}")
        return _extractive_recall_notes(list(source_chunks or []))


def recommendation_agent(state: AssessmentState, fast: bool = False) -> dict:
    """
    Recommendation Agent.
    Input:  state['topic_scores'], state['answers'], state['chroma_collection_id']
    Output: state['weak_topics'], state['strong_topics'], state['recommendations']
    """
    logger.info(f"[RecommendationAgent] Starting | session={state['session_id']}")
    topic_scores = state.get("topic_scores", {})
    logs = list(state.get("agent_logs", []))
    resource_map = _load_resource_map()
    collection_id = state.get("chroma_collection_id", "")

    llm = None if fast else LlmService()
    rag = None if fast else RagService()

    weak_topics = []
    strong_topics = []
    recommendations = []
    questions = state.get("questions", [])
    answers = state.get("answers", [])
    subject = state.get("subject", "Sri Lankan G.C.E. A/L Biology")

    # Calculate the terminal attempt count per question/topic. Attempt records
    # contain cumulative values (1, 2, 3, 4), so averaging every record would
    # exaggerate weakness; the final attempt number is the meaningful signal.
    topic_attempts = {}
    for a in answers:
        if not (a.get("is_terminal") or a.get("is_correct") or a.get("attempts", 0) >= 4):
            continue
        q_id = a.get("q_id")
        q = next((q for q in questions if q.get("q_id") == q_id), {})
        t = q.get("topic")
        if not t:
            continue
        if t not in topic_attempts:
            topic_attempts[t] = {"attempts": 0, "count": 0}
        topic_attempts[t]["attempts"] += a.get("attempts", 1)
        topic_attempts[t]["count"] += 1

    for topic, scores in topic_scores.items():
        total = scores.get("total", 0)
        correct = scores.get("correct", 0)
        if total == 0:
            continue
        ratio = correct / total
        
        # A topic is considered weak if accuracy < THRESHOLD OR if average attempts > 1.0
        avg_attempts = 1.0
        if topic in topic_attempts and topic_attempts[topic]["count"] > 0:
            avg_attempts = topic_attempts[topic]["attempts"] / topic_attempts[topic]["count"]

        if ratio < WEAK_THRESHOLD or avg_attempts > 1.0:
            weak_topics.append(topic)

    # A/A+ learners still receive one clearly-labelled extension card, without
    # falsely calling a fully-mastered topic a weak area.
    enrichment_topics = []
    if not weak_topics and topic_scores:
        best_fallback = max(
            topic_scores,
            key=lambda t: (
                topic_scores[t].get("correct", 0) / max(topic_scores[t].get("total", 1), 1),
                -topic_attempts.get(t, {}).get("attempts", 1),
            ),
        )
        enrichment_topics.append(best_fallback)

    def _build_topic_recommendation(topic: str) -> dict:
        scores = topic_scores.get(topic, {})
        total = scores.get("total", 0)
        correct = scores.get("correct", 0)
        ratio = correct / total if total else 0.0

        # Generate concept notes from student's own material
        topic_source_chunks = []
        seen_chunk_ids = set()
        for question in questions:
            if question.get("topic") != topic:
                continue
            for chunk in question.get("source_chunks", []):
                chunk_id = str(chunk.get("chunk_id", ""))
                if chunk_id and chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    topic_source_chunks.append(chunk)
            explanation = str(question.get("model_answer", "")).strip()
            if explanation:
                synthetic_id = f"explanation:{question.get('q_id', '')}"
                if synthetic_id not in seen_chunk_ids:
                    seen_chunk_ids.add(synthetic_id)
                    topic_source_chunks.append({
                        "chunk_id": synthetic_id,
                        "text": explanation,
                        "source": question.get("source_file", "Quiz explanation"),
                        "page": question.get("page_number", 0),
                    })
        curated = _curated_resources(topic, resource_map)
        resource_executor = None
        resource_future = None
        if not fast and not curated:
            resource_executor = ThreadPoolExecutor(max_workers=1)
            resource_future = resource_executor.submit(build_resources, topic)

        if fast:
            concept_notes = _extractive_recall_notes(topic_source_chunks)
        else:
            concept_notes = _generate_concept_notes(
                topic,
                rag,
                llm,
                collection_id,
                subject,
                source_chunks=topic_source_chunks,
            )

        # Priority 1: hand-curated resource_map (pre-verified, no network wait) —
        # skip the expensive live scrape entirely when we already have exact links.
        if fast:
            resources = curated
        elif curated:
            resources = curated
            logger.info(f"[RecommendationAgent] '{topic}': using curated resources (scrape skipped)")
        else:
            # Priority 2: web scrape to find SPECIFIC article/video URLs
            # — GFG: exact article via DDG site:geeksforgeeks.org search
            # — TutorialsPoint: exact tutorial via DDG site:tutorialspoint.com search
            # — YouTube: specific video ID from search results page JSON
            logger.info(f"[RecommendationAgent] '{topic}': scraping specific resource URLs...")
            resources = resource_future.result() if resource_future else []
            if resource_executor:
                resource_executor.shutdown(wait=False)
            logger.info(
                f"[RecommendationAgent] '{topic}': scraped {len(resources)} resources "
                f"({[r['source'] for r in resources]})"
            )

        return {
            "topic":         topic,
            "recommendation_type": "review" if topic in weak_topics else "enrichment",
            "score_ratio":   round(ratio, 2),
            "percentage":    round(ratio * 100, 1),
            "concept_notes": concept_notes,
            "resources":     resources[:4],
        }

    topics_to_process = [*weak_topics, *enrichment_topics]
    if topics_to_process:
        # Each topic's concept-note generation + resource lookup is dominated by
        # blocking network I/O (LLM call, web scraping). Running topics
        # concurrently turns the wall-clock cost from sum(topics) into
        # roughly max(topics), which is the difference between a multi-minute
        # wait and a usable one for students with several weak areas.
        with ThreadPoolExecutor(max_workers=min(5, len(topics_to_process))) as executor:
            recommendations = list(executor.map(_build_topic_recommendation, topics_to_process))

    strong_topics = [topic for topic in topic_scores if topic not in weak_topics]

    logs.append(f"[RecommendationAgent] Weak={len(weak_topics)} Strong={len(strong_topics)}")
    logger.info(f"[RecommendationAgent] Done | weak={len(weak_topics)} topics")

    return {
        "weak_topics":     weak_topics,
        "strong_topics":   strong_topics,
        "recommendations": recommendations,
        "agent_logs":      logs,
    }
