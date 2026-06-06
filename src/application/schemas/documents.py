"""Pydantic schemas for document-analysis endpoints."""

from typing import Any

from pydantic import BaseModel


class AnalysisResultResponse(BaseModel):
    """Result returned after AI document classification and extraction."""

    document_id: str
    doc_type: str
    confidence: float
    extracted_data: dict[str, Any] | None
    ai_model: str
    fallback_used: bool = False
    fallback_reason: str | None = None
