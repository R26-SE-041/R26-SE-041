"""
Recommendation Agent — Identifies weak topics and returns
curated learning resources from trusted educational sources.
"""
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from app.graph.state import AssessmentState

load_dotenv()
logger = logging.getLogger(__name__)

WEAK_THRESHOLD = float(os.getenv("WEAK_TOPIC_THRESHOLD", "0.60"))

# Load resource map from JSON file
_RESOURCE_MAP_PATH = Path(__file__).parent.parent / "data" / "resources" / "resource_map.json"

def _load_resource_map() -> dict:
    try:
        with open(_RESOURCE_MAP_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load resource_map.json: {e}")
        return {}


def _find_resources(topic: str, resource_map: dict) -> list:
    """Find curated resources for a topic using fuzzy keyword matching."""
    topic_lower = topic.lower()
    matched = []
    for key, resources in resource_map.items():
        if key.lower() in topic_lower or topic_lower in key.lower():
            matched.extend(resources)
    if not matched:
        # Fallback: GeeksforGeeks search
        search_query = topic.replace(" ", "+")
        matched = [{
            "title": f"GeeksforGeeks: {topic}",
            "url": f"https://www.geeksforgeeks.org/?s={search_query}",
            "type": "search"
        }]
    return matched[:3]  # Max 3 resources per topic


def recommendation_agent(state: AssessmentState) -> dict:
    """
    Recommendation Agent.
    Input:  state['topic_scores'], state['answers']
    Output: state['weak_topics'], state['strong_topics'], state['recommendations']
    """
    logger.info(f"[RecommendationAgent] Starting | session={state['session_id']}")
    topic_scores = state.get("topic_scores", {})
    logs = list(state.get("agent_logs", []))
    resource_map = _load_resource_map()

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
            resources = _find_resources(topic, resource_map)
            recommendations.append({
                "topic":       topic,
                "score_ratio": round(ratio, 2),
                "percentage":  round(ratio * 100, 1),
                "resources":   resources
            })
        else:
            strong_topics.append(topic)

    logs.append(f"[RecommendationAgent] Weak={len(weak_topics)} Strong={len(strong_topics)}")
    logger.info(f"[RecommendationAgent] Done | weak={len(weak_topics)} topics")

    return {
        "weak_topics":     weak_topics,
        "strong_topics":   strong_topics,
        "recommendations": recommendations,
        "agent_logs":      logs
    }
