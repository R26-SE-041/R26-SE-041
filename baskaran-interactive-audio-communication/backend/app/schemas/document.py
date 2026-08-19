"""Pydantic schemas for document upload, management, and RAG queries."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    filename: str
    file_type: str
    storage_path: str
    chunk_count: int
    uploaded_at: datetime


class DocumentListItem(BaseModel):
    document_id: UUID
    filename: str
    file_type: str = "pdf"
    chunk_count: int
    uploaded_at: datetime


class ChunkReference(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    page: int | None = None
    excerpt: str = Field(..., description="Short excerpt of the matched chunk")
    score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")


class AskRequest(BaseModel):
    transcript: str = Field(..., description="Raw or transcribed question from user")
    language: str = Field(default="english", description="Response language")
    enhanced_query: str | None = Field(
        default=None,
        description="If provided, skip prompt enhancement and use this query directly",
    )


class EnhanceRequest(BaseModel):
    transcript: str = Field(..., description="Raw transcript to enhance")
    language: str = Field(default="english", description="Language of the query")


class EnhanceResponse(BaseModel):
    enhanced_query: str


class AskResponse(BaseModel):
    answer: str
    enhanced_query: str | None = None
    references: list[ChunkReference] = []
