from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title="Image Enhancement & OCR API",
    description=(
        "Enhances low-quality images with SRCNN (Modal.com serverless) "
        "then extracts text via TrOCR (Modal.com serverless)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"message": "Image Enhancement & OCR API — see /docs"}
