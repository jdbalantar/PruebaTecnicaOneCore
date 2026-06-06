"""Gemini implementation of IDocumentAIPort using Google Generative Language API."""

import base64
import json
import time
from typing import Any

import httpx

from src.domain.exceptions import AIServiceError
from src.domain.models.document import (
    DocumentType,
    InformationData,
    InvoiceData,
    InvoiceProduct,
    Sentiment,
)
from src.domain.ports.document_ai import IDocumentAIPort
from src.infrastructure.ai.json_utils import parse_json_object

_CLASSIFY_SYSTEM_PROMPT = (
    "You are a document classifier. Classify the document as either 'invoice' "
    "(contains financial/economic transaction data) or 'information' "
    "(general text, reports, informational content). "
    "Respond ONLY with valid JSON: "
    '{"type": "invoice|information", "confidence": 0.0-1.0, "reasoning": "brief explanation"}'
)

_INVOICE_SYSTEM_PROMPT = (
    "You are a data extraction assistant. Extract structured invoice data from the "
    "document and respond ONLY with valid JSON matching this schema exactly: "
    '{"client_name": "", "client_address": "", "supplier_name": "", '
    '"supplier_address": "", "invoice_number": "", "date": "", '
    '"products": [{"quantity": 0, "name": "", "unit_price": 0.0, "total": 0.0}], '
    '"total": 0.0}'
)

_INFO_SYSTEM_PROMPT = (
    "You are a data extraction assistant. Extract structured information from the "
    "document and respond ONLY with valid JSON matching this schema exactly: "
    '{"description": "", "summary": "", "sentiment": "positive|negative|neutral"}'
)

_MAX_RETRIES = 3
_RETRY_DELAYS = [1, 2, 4]


class GeminiDocumentAdapter(IDocumentAIPort):
    """Gemini implementation for document classification and extraction."""

    def __init__(self, settings) -> None:
        if not settings.GEMINI_API_KEY:
            raise AIServiceError(
                "GEMINI_API_KEY is not configured. "
                "Set GEMINI_API_KEY in environment variables."
            )

        self._api_key: str = settings.GEMINI_API_KEY
        self._base_url: str = settings.GEMINI_API_BASE.rstrip("/")
        self._classify_model: str = settings.GEMINI_MODEL_CLASSIFY
        self._extract_model: str = settings.GEMINI_MODEL_EXTRACT

    def classify_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[DocumentType, float]:
        payload = self._build_payload(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            instruction=_CLASSIFY_SYSTEM_PROMPT,
        )
        raw = self._call_with_retry(model=self._classify_model, payload=payload)
        return self._parse_classify_response(raw)

    def extract_invoice_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InvoiceData:
        payload = self._build_payload(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            instruction=_INVOICE_SYSTEM_PROMPT,
        )
        raw = self._call_with_retry(model=self._extract_model, payload=payload)
        return self._parse_invoice_response(raw)

    def extract_info_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InformationData:
        payload = self._build_payload(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            instruction=_INFO_SYSTEM_PROMPT,
        )
        raw = self._call_with_retry(model=self._extract_model, payload=payload)
        return self._parse_info_response(raw)

    def _build_payload(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        instruction: str,
    ) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"text": instruction}]

        if content_type in ("image/jpeg", "image/png", "application/pdf"):
            parts.append(
                {
                    "inline_data": {
                        "mime_type": content_type,
                        "data": base64.b64encode(file_bytes).decode("utf-8"),
                    }
                }
            )

        parts.append(
            {
                "text": (
                    f"Filename: {filename}. "
                    "Return ONLY valid JSON with no markdown fences."
                )
            }
        )

        return {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }

    def _call_with_retry(self, model: str, payload: dict[str, Any]) -> str:
        last_exc: Exception | None = None
        endpoint = f"{self._base_url}/models/{model}:generateContent"

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = httpx.post(
                    endpoint,
                    headers={"x-goog-api-key": self._api_key},
                    json=payload,
                    timeout=45.0,
                )

                if response.status_code == 404:
                    raise AIServiceError(
                        "Gemini endpoint/model not found (404). "
                        f"Check GEMINI_API_BASE and model '{model}'. "
                        f"Response: {response.text}"
                    )

                if response.status_code == 429:
                    raise AIServiceError(
                        f"Gemini rate limit exceeded (429): {response.text}"
                    )

                response.raise_for_status()
                return self._extract_text_from_response(response.json())
            except (httpx.TimeoutException, httpx.HTTPError, AIServiceError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAYS[attempt])
                    continue
                break

        raise AIServiceError(
            f"Gemini request failed after {_MAX_RETRIES} retries: {last_exc}"
        ) from last_exc

    @staticmethod
    def _extract_text_from_response(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise AIServiceError(f"Gemini returned no candidates: {payload}")

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            raise AIServiceError(f"Gemini returned empty content parts: {payload}")

        text = parts[0].get("text")
        if not isinstance(text, str) or not text.strip():
            raise AIServiceError(f"Gemini returned empty text payload: {payload}")

        return text

    @staticmethod
    def _parse_classify_response(raw: str) -> tuple[DocumentType, float]:
        data = parse_json_object(raw, "Classification")

        type_str = str(data.get("type", "")).lower()
        confidence = float(data.get("confidence", 0.5))

        if type_str == "invoice":
            return DocumentType.INVOICE, confidence
        if type_str == "information":
            return DocumentType.INFORMATION, confidence
        return DocumentType.UNKNOWN, confidence

    @staticmethod
    def _parse_invoice_response(raw: str) -> InvoiceData:
        data = parse_json_object(raw, "Invoice extraction")

        products = [
            InvoiceProduct(
                quantity=float(p.get("quantity", 0)),
                name=str(p.get("name", "")),
                unit_price=float(p.get("unit_price", 0.0)),
                total=float(p.get("total", 0.0)),
            )
            for p in data.get("products", [])
        ]
        return InvoiceData(
            client_name=data.get("client_name", ""),
            client_address=data.get("client_address", ""),
            supplier_name=data.get("supplier_name", ""),
            supplier_address=data.get("supplier_address", ""),
            invoice_number=data.get("invoice_number", ""),
            date=data.get("date", ""),
            products=products,
            total=float(data.get("total", 0.0)),
        )

    @staticmethod
    def _parse_info_response(raw: str) -> InformationData:
        data = parse_json_object(raw, "Info extraction")

        sentiment_raw = str(data.get("sentiment", "neutral")).lower()
        try:
            sentiment = Sentiment(sentiment_raw)
        except ValueError:
            sentiment = Sentiment.NEUTRAL

        return InformationData(
            description=data.get("description", ""),
            summary=data.get("summary", ""),
            sentiment=sentiment,
        )

