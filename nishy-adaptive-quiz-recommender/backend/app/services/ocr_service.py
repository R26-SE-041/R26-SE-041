"""
OCR Service — Extract text from images using pytesseract.
Note: Qwen2.5-7B is text-only. For Phase 1, images use pytesseract fallback.
Phase 2 could add a multimodal model (e.g., Qwen2-VL) on Modal for better OCR.
"""
import os
import logging
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class OcrService:
    """
    Extracts text from images using pytesseract (Tesseract OCR).
    Handles: printed text, scanned documents, screenshots.
    For handwriting/diagrams, Phase 2 will add Qwen2-VL multimodal.
    """

    def extract_with_gemini(self, image_path: str) -> List[Dict]:
        """
        Primary OCR extraction.
        Name kept for backward compatibility with ingestion_agent.
        Uses pytesseract (no API key required).
        """
        return self._tesseract_ocr(image_path)

    def _tesseract_ocr(self, image_path: str) -> List[Dict]:
        """Extract text using pytesseract."""
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(image_path)
            # Convert to RGB if needed (handles PNG with alpha)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            text = pytesseract.image_to_string(image, config="--oem 3 --psm 6")
            if text.strip():
                logger.info(f"OCR extracted {len(text)} chars from {Path(image_path).name}")
                return [{
                    "chunk_id": f"ocr_{Path(image_path).stem}",
                    "text": text.strip(),
                    "source": Path(image_path).name,
                    "page": 1,
                    "heading": "Image Content",
                }]
        except ImportError:
            logger.warning("pytesseract not installed. Skipping image: %s", image_path)
        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
        return []

    def evaluate_diagram_answer(self, question: dict, image_path: str) -> dict:
        """
        Diagram evaluation — Phase 2 feature.
        Returns neutral score for now.
        """
        logger.info("Diagram evaluation not available in Phase 1 — returning neutral score")
        return {
            "score": 0.5,
            "marks_breakdown": {},
            "missing_elements": [],
            "feedback": "Diagram evaluation is a Phase 2 feature. Manual review required.",
            "is_correct": False,
        }
