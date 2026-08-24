"""
Recommendation Agent — Identifies weak topics and returns:
1. LLM-generated concept notes (bullet points) for each weak topic
2. Curated multilingual learning resource links (English / Tamil / Sinhala)
"""
import os
import json
import logging
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv
from app.graph.state import AssessmentState
from app.services.llm_service import LlmService
from app.services.rag_service import RagService

load_dotenv()
logger = logging.getLogger(__name__)

WEAK_THRESHOLD = float(os.getenv("WEAK_TOPIC_THRESHOLD", "0.60"))

# Load resource map from JSON file
_RESOURCE_MAP_PATH = Path(__file__).parent.parent / "data" / "resources" / "resource_map.json"


CONCEPT_NOTES_PROMPT = """You are a university lecturer at SLIIT, Sri Lanka. A student struggled with the topic "{topic}" in their quiz.

Use the following material from their uploaded study notes:
{context}

Write a clear, concise concept summary to help the student understand "{topic}".

Format your response as exactly 4-6 bullet points. Each bullet point must:
- Start with a bold keyword (e.g. **Keyword**: explanation)
- Be a self-contained, meaningful explanation (1-2 sentences max per bullet)
- Use simple, clear language suitable for university-level students
- Focus on the core concept the student is weak in

Do NOT include:
- Any intro/outro sentences
- Headers or section titles
- Numbered lists
- The phrase "the uploaded material" or "the document"

Return ONLY the bullet points, nothing else."""


def _load_resource_map() -> dict:
    try:
        with open(_RESOURCE_MAP_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load resource_map.json: {e}")
        return {}


def _find_resources(topic: str, resource_map: dict) -> list:
    """Find curated multilingual resources for a topic, with English/Tamil/Sinhala labels."""
    topic_lower = topic.lower()

    # Try exact/partial keyword match from resource_map
    matched_raw = []
    for key, resources in resource_map.items():
        if key.lower() in topic_lower or topic_lower in key.lower():
            matched_raw.extend(resources)

    # Build structured multilingual resource objects
    structured = []
    for r in matched_raw[:3]:
        lang = r.get("language", "english").lower()
        label = {"english": "English", "tamil": "Tamil", "sinhala": "Sinhala"}.get(lang, "English")
        structured.append({
            "label":   label,
            "title":   r.get("title", topic),
            "url":     r.get("url", ""),
            "source":  r.get("source", "GeeksforGeeks"),
        })

    # If no mapped resources found, generate fallback links
    if not structured:
        encoded = urllib.parse.quote_plus(topic)          # proper URL encoding
        yt_encoded = urllib.parse.quote(topic)            # %20 style for YouTube
        structured = [
            {
                "label":  "English",
                "title":  f"{topic} – GeeksforGeeks",
                "url":    f"https://www.geeksforgeeks.org/search/?q={encoded}",
                "source": "GeeksforGeeks",
            },
            {
                "label":  "English",
                "title":  f"{topic} – TutorialsPoint",
                "url":    f"https://www.tutorialspoint.com/search/search_result.htm?search={encoded}",
                "source": "TutorialsPoint",
            },
            {
                "label":  "English",
                "title":  f"{topic} Tutorial – YouTube",
                "url":    f"https://www.youtube.com/results?search_query={yt_encoded}+tutorial",
                "source": "YouTube",
            },
        ]

    return structured


def _generate_concept_notes(topic: str, rag: RagService, llm: LlmService,
                              collection_id: str) -> list[str]:
    """Generate bullet-point concept notes for a weak topic using RAG context."""
    try:
        chunks = rag.retrieve(collection_id, topic, k=4)
        context = "\n\n".join([c["text"] for c in chunks]) if chunks else ""
        if not context:
            context = f"General knowledge about {topic}."

        prompt = CONCEPT_NOTES_PROMPT.format(topic=topic, context=context)
        raw = llm.call(prompt, temperature=0.2)

        # Parse bullet points — lines starting with - or •
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
        bullets = [l for l in lines if l.startswith("-") or l.startswith("•") or l.startswith("*")]

        # Fallback: if model didn't use bullet format, treat each sentence as a bullet
        if not bullets:
            bullets = [f"- {l}" for l in lines[:6] if len(l) > 15]

        # Clean up and return max 6 bullets
        cleaned = []
        for b in bullets[:6]:
            b = b.lstrip("-•* ").strip()
            if b:
                cleaned.append(b)
        return cleaned if cleaned else [f"Review the core concepts of {topic} from your study material."]

    except Exception as e:
        logger.error(f"[RecommendationAgent] Concept notes failed for '{topic}': {e}")
        return [f"Review the core concepts of {topic} from your study material."]


def recommendation_agent(state: AssessmentState) -> dict:
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

    llm = LlmService()
    rag = RagService()

    weak_topics = []
    strong_topics = []
    recommendations = []

    for topic, scores in topic_scores.items():
        total = scores.get("total", 0)
        correct = scores.get("correct", 0)
        if total == 0:
            continue
        ratio = correct / total

        if ratio < WEAK_THRESHOLD:
            weak_topics.append(topic)

            # Generate concept notes from student's own material
            concept_notes = _generate_concept_notes(topic, rag, llm, collection_id)

            # Get multilingual resource links
            resources = _find_resources(topic, resource_map)

            recommendations.append({
                "topic":         topic,
                "score_ratio":   round(ratio, 2),
                "percentage":    round(ratio * 100, 1),
                "concept_notes": concept_notes,
                "resources":     resources,
            })
        else:
            strong_topics.append(topic)

    logs.append(f"[RecommendationAgent] Weak={len(weak_topics)} Strong={len(strong_topics)}")
    logger.info(f"[RecommendationAgent] Done | weak={len(weak_topics)} topics")

    return {
        "weak_topics":     weak_topics,
        "strong_topics":   strong_topics,
        "recommendations": recommendations,
        "agent_logs":      logs,
    }
