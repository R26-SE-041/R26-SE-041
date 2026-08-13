"""
Ingestion Agent — Converts uploaded files into ChromaDB-stored chunks.
Supports: PDF, DOCX, PPTX, Images (OCR), TXT
"""
import os
import logging
from typing import List
from pathlib import Path
from dotenv import load_dotenv

from app.services.rag_service import RagService
from app.services.ocr_service import OcrService
from app.graph.state import AssessmentState

load_dotenv()
logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {
    "pdf":  "pdf",
    "docx": "docx",
    "pptx": "pptx",
    "txt":  "txt",
    "jpg":  "image",
    "jpeg": "image",
    "png":  "image",
}


def ingestion_agent(state: AssessmentState) -> dict:
    """
    Ingestion Agent.
    Input:  state['document_ids'], state['session_id']
    Output: state['chroma_collection_id'], state['ingestion_status']
    """
    logger.info(f"[IngestionAgent] Starting | session={state['session_id']}")
    rag = RagService()
    collection_id = state["session_id"]
    document_ids = state.get("document_ids", [])
    logs = list(state.get("agent_logs", []))

    if not document_ids:
        return {
            "ingestion_status": "error",
            "error": "No documents selected.",
            "agent_logs": logs
        }

    # Merge chunks from the selected document collections into the session collection
    source_collections = [f"doc_{doc_id}" for doc_id in document_ids]
    try:
        rag.merge_collections(collection_id, source_collections)
        logs.append(f"[IngestionAgent] Merged {len(document_ids)} documents into session collection '{collection_id}'")
    except Exception as e:
        return {
            "ingestion_status": "error",
            "error": f"Failed to merge document collections: {str(e)}",
            "agent_logs": logs
        }

    logger.info(f"[IngestionAgent] Done merging documents")
    return {
        "chroma_collection_id": collection_id,
        "ingestion_status": "done",
        "agent_logs": logs
    }
