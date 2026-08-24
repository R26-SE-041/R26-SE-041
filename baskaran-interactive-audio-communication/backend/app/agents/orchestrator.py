"""
LangGraph Orchestrator — wires all agent nodes into a single StateGraph.

Graph topology (linear for Phase 1, extendable):

    START → stt → prompt_enhancer → rag → localization → tts → END

Phase 1: only stt node is fully wired; others are in the graph
but will gracefully degrade if their Modal endpoints aren't deployed.

Usage:
    graph = build_graph()
    result = await graph.ainvoke(initial_state)
"""

from langgraph.graph import StateGraph, END

from app.agents.stt_agent import stt_node
from app.agents.prompt_agent import prompt_agent_node
from app.agents.rag_agent import rag_agent_node
from app.agents.localization_agent import localization_node
from app.agents.tts_agent import tts_node
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_graph() -> StateGraph:
    """Build and compile the VoiceLearn LangGraph pipeline."""
    graph = StateGraph(dict)

    # Register nodes
    graph.add_node("stt", stt_node)
    graph.add_node("prompt_enhancer", prompt_agent_node)
    graph.add_node("rag", rag_agent_node)
    graph.add_node("localization", localization_node)
    graph.add_node("tts", tts_node)

    # Linear edges
    graph.set_entry_point("stt")
    graph.add_edge("stt", "prompt_enhancer")
    graph.add_edge("prompt_enhancer", "rag")
    graph.add_edge("rag", "localization")
    graph.add_edge("localization", "tts")
    graph.add_edge("tts", END)

    return graph.compile()


# Phase 1: STT-only graph (used by /voice/transcribe endpoint)
def build_stt_only_graph() -> StateGraph:
    """Minimal graph for Phase 1 — STT only, no RAG."""
    graph = StateGraph(dict)
    graph.add_node("stt", stt_node)
    graph.set_entry_point("stt")
    graph.add_edge("stt", END)
    return graph.compile()
