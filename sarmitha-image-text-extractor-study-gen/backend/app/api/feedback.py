import base64
import os
import time
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/feedback")

DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dataset")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
METADATA_FILE = os.path.join(DATASET_DIR, "metadata.jsonl")

# Ensure dataset directories exist
os.makedirs(IMAGES_DIR, exist_ok=True)

class FeedbackRequest(BaseModel):
    crop_b64: str
    corrected_text: str

@router.post("/ocr")
async def submit_ocr_feedback(req: FeedbackRequest):
    """
    Saves a cropped image and its corrected text to the local dataset for fine-tuning.
    """
    if not req.corrected_text.strip():
        raise HTTPException(status_code=400, detail="Corrected text cannot be empty.")
    
    if not req.crop_b64:
        raise HTTPException(status_code=400, detail="Image crop cannot be empty.")

    try:
        # Decode image
        image_bytes = base64.b64decode(req.crop_b64)
        
        # Generate unique filename based on timestamp
        timestamp = int(time.time() * 1000)
        filename = f"crop_{timestamp}.jpg"
        image_path = os.path.join(IMAGES_DIR, filename)
        
        # Save image
        with open(image_path, "wb") as f:
            f.write(image_bytes)
            
        # Append to metadata.jsonl
        # HuggingFace ImageFolder format: {"file_name": "images/crop_xxx.jpg", "text": "corrected text"}
        metadata_entry = {
            "file_name": f"images/{filename}",
            "text": req.corrected_text.strip()
        }
        
        with open(METADATA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(metadata_entry, ensure_ascii=False) + "\n")
            
        return JSONResponse({"status": "success", "message": "Feedback saved successfully."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {str(e)}")
