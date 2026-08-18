"""
Upload Router — Handle file uploads and trigger ingestion.
"""
import os
import uuid
import shutil
import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".jpg", ".jpeg", ".png"}


@router.post("/")
async def upload_files(
    files: List[UploadFile] = File(...)
):
    """
    Upload one or more study material files.
    Returns list of saved file paths for use in session creation.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_paths = []

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}"
            )

        # Check file size
        content = await file.read()
        if len(content) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' exceeds {MAX_FILE_MB}MB limit."
            )

        # Save with unique name
        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(save_path, "wb") as f:
            f.write(content)

        saved_paths.append(save_path)
        logger.info(f"Uploaded: {file.filename} -> {save_path}")

    return {
        "uploaded": len(saved_paths),
        "file_paths": saved_paths,
        "message": f"{len(saved_paths)} file(s) uploaded successfully."
    }
