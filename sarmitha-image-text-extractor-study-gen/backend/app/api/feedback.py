import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.auth import AuthUser, pipeline_user
from app.services.persistence import PersistenceError, save_feedback

router = APIRouter(prefix="/api/feedback")


class FeedbackRequest(BaseModel):
    crop_b64: str
    corrected_text: str = Field(min_length=1, max_length=10000)


@router.post("/ocr")
async def submit_ocr_feedback(req: FeedbackRequest, user: AuthUser | None = Depends(pipeline_user)):
    text = req.corrected_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Corrected text cannot be empty.")
    if len(req.crop_b64) > ((settings.max_upload_bytes + 2) // 3) * 4:
        raise HTTPException(status_code=413, detail="Image crop is too large.")
    try:
        image = base64.b64decode(req.crop_b64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=400, detail="Image crop must be valid base64.")
    if not image:
        raise HTTPException(status_code=400, detail="Image crop cannot be empty.")
    if len(image) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image crop is too large.")
    try:
        feedback_id = await save_feedback(image, text, user)
    except (PersistenceError, OSError):
        raise HTTPException(status_code=503, detail="Could not save feedback. Please try again.")
    return {"status": "success", "message": "Feedback saved successfully.", "id": feedback_id}
