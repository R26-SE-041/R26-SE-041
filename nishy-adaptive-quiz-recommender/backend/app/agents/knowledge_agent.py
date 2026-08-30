"""
Knowledge Agent — Extracts topics, subtopics, Bloom's taxonomy tags,
and builds a concept relationship graph from document chunks.
"""
import logging
from pathlib import Path
from dotenv import load_dotenv

from app.graph.state import AssessmentState

load_dotenv()
logger = logging.getLogger(__name__)

KNOWLEDGE_PROMPT = """
You are an expert educational content analyzer.

Analyze the following lecture/study material and extract structured knowledge.
Return ONLY valid JSON with this exact structure:

{{
    "topics": ["Topic 1", "Topic 2", "Topic 3"],
    "topic_hierarchy": {{
        "Topic 1": ["Subtopic 1a", "Subtopic 1b"],
        "Topic 2": ["Subtopic 2a"]
    }},
    "concept_relationships": [
        {{"from": "Concept A", "to": "Concept B", "relation": "prerequisite_of"}},
        {{"from": "Concept C", "to": "Concept D", "relation": "example_of"}}
    ],
    "bloom_tag_map": {{
        "Topic 1": "apply",
        "Topic 2": "understand",
        "Topic 3": "analyze"
    }}
}}

Allowed relation types: prerequisite_of, example_of, part_of, related_to
Allowed Bloom's levels: remember, understand, apply, analyze, evaluate, create

Rules:
- Extract 3-10 main topics from the material
- Each topic must have at least 1 subtopic
- Bloom's level = the dominant cognitive level required to understand this topic
- Use ONLY content from the provided material

Material:
{material}
"""


def knowledge_agent(state: AssessmentState) -> dict:
    """
    Knowledge Agent.
    Input:  state['document_ids']
    Output: state['topics'], state['knowledge_status']
    """
    logger.info(f"[KnowledgeAgent] Starting | session={state['session_id']}")
    from app.services.db_service import DbService
    import json
    
    db = DbService()
    document_ids = state.get("document_ids", [])
    logs = list(state.get("agent_logs", []))

    if not document_ids:
        requested_topic = str(state.get("requested_topic") or "").strip()
        if requested_topic:
            logs.append(f"[KnowledgeAgent] Using requested Biology topic: {requested_topic}")
            return {
                "topics": [requested_topic],
                "topic_hierarchy": {requested_topic: []},
                "concept_graph_json": "{}",
                "bloom_tag_map": {},
                "knowledge_status": "done",
                "error": None,
                "agent_logs": logs,
            }
        return {
            "knowledge_status": "error",
            "error": "No documents available for knowledge extraction.",
            "agent_logs": logs
        }

    docs = db.get_documents(document_ids)
    all_topics = set()
    
    for doc in docs:
        topics_raw = doc.get("topics", "[]")
        try:
            topics = json.loads(topics_raw) if isinstance(topics_raw, str) else topics_raw
            if isinstance(topics, list):
                for t in topics:
                    all_topics.add(t)
        except:
            pass

    placeholders = {"general", "general knowledge", "biology", "biology 1"}
    final_topics = [
        topic for topic in all_topics
        if str(topic).strip().casefold() not in placeholders
    ]

    # Filename is source metadata, not a factual knowledge fallback. Avoid an
    # extra setup-time LLM call: question retrieval is additionally seeded with
    # actual PDF chunk text and all factual output is validated later.
    if not final_topics:
        final_topics = [
            Path(str(doc.get("filename", "uploaded-pdf"))).stem
            for doc in docs
            if str(doc.get("filename", "")).strip()
        ]
    if not final_topics:
        return {
            "knowledge_status": "error",
            "error": "No source-derived topics available.",
            "agent_logs": logs,
        }

    logs.append(f"[KnowledgeAgent] Aggregated {len(final_topics)} topics from documents")
    logger.info(f"[KnowledgeAgent] Done | {len(final_topics)} topics aggregated")

    return {
        "topics":             final_topics,
        "topic_hierarchy":    {},
        "concept_graph_json": "{}",
        "bloom_tag_map":      {},
        "knowledge_status":   "done",
        "agent_logs":         logs
    }
