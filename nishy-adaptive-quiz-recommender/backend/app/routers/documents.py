from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from typing import List
import os
import uuid
import json
from pathlib import Path
from pydantic import BaseModel

from app.services.db_service import DbService
from app.services.rag_service import RagService
from app.services.ocr_service import OcrService
from app.services.llm_service import LlmService
from app.agents.ingestion_agent import SUPPORTED_FORMATS

router = APIRouter()

class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    topics: List[str]
    chunk_count: int
    created_at: str

@router.get("/", response_model=List[DocumentResponse])
async def list_documents():
    db = DbService()
    docs = db.get_all_documents()
    res = []
    for d in docs:
        topics = json.loads(d["topics"]) if isinstance(d["topics"], str) else d["topics"]
        res.append({
            "document_id": d["document_id"],
            "filename": d["filename"],
            "topics": topics,
            "chunk_count": d["chunk_count"],
            "created_at": d["created_at"]
        })
    return res

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    db = DbService()
    rag = RagService()
    ocr = OcrService()
    llm = LlmService()
    
    document_id = str(uuid.uuid4())
    upload_dir = Path(f"./data/uploads/{document_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    ext = Path(file_path).suffix.lstrip(".").lower()
    file_type = SUPPORTED_FORMATS.get(ext)
    
    if file_type is None:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{ext}'")
        
    # Extract
    try:
        if file_type == "pdf":
            chunks = rag.extract_pdf(str(file_path))
        elif file_type == "docx":
            chunks = rag.extract_docx(str(file_path))
        elif file_type == "pptx":
            chunks = rag.extract_pptx(str(file_path))
        elif file_type == "txt":
            chunks = rag.extract_txt(str(file_path))
        elif file_type == "image":
            chunks = ocr.extract_with_gemini(str(file_path))
        else:
            chunks = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {str(e)}")
        
    if not chunks:
        raise HTTPException(status_code=400, detail="No content could be extracted.")
        
    # Embed
    collection_id = f"doc_{document_id}"
    try:
        rag.embed_and_store(collection_id, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
        
    # Extract basic topics to save in DB
    full_text = "\n\n".join([c["text"] for c in chunks])
    if len(full_text) > 25000:
        full_text = full_text[:25000]
        
    prompt = f"""
    Extract 3-10 main topics from the following material.
    Return ONLY valid JSON: {{"topics": ["Topic 1", "Topic 2"]}}
    Material:
    {full_text}
    """
    
    try:
        data = llm.call_json(prompt)
        topics = data.get("topics", [])
    except:
        topics = ["General"]
        
    doc_record = {
        "document_id": document_id,
        "filename": file.filename,
        "topics": json.dumps(topics),
        "chunk_count": len(chunks)
    }
    
    db.save_document(doc_record)
    
    return {
        "document_id": document_id,
        "message": "Upload complete",
        "topics": topics
    }
