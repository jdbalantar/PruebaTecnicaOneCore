"""OpenAI implementation of IDocumentAIPort."""

import base64
import json
import re
import time
from typing import Any

import openai

from src.domain.exceptions import AIServiceError
from src.domain.models.document import (
    DocumentType,
    InformationData,
    InvoiceData,
    InvoiceProduct,
    Sentiment,
)
from src.domain.ports.document_ai import IDocumentAIPort

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
_RETRY_DELAYS = [1, 2, 4]  # seconds between successive retry attempts


class OpenAIDocumentAdapter(IDocumentAIPort):
    """OpenAI implementation of IDocumentAIPort.

    Uses GPT-4o-mini for classification and GPT-4o for extraction.
    Images are processed via the vision API; PDFs use a lightweight
    text-extraction heuristic to build a text-based prompt.

    Args:
        settings: Application settings instance providing
            ``OPENAI_API_KEY``, ``OPENAI_MODEL_CLASSIFY``, and
            ``OPENAI_MODEL_EXTRACT``.

    Raises:
        AIServiceError: On construction if ``OPENAI_API_KEY`` is absent.
    """

    def __init__(self, settings) -> None:
        """Initialise the OpenAI client from application settings.

        Args:
            settings: Populated Settings instance with OpenAI credentials.

        Raises:
            AIServiceError: If ``OPENAI_API_KEY`` is empty or None.
        """
        if not settings.OPENAI_API_KEY:
            raise AIServiceError(
                "OPENAI_API_KEY is not configured. "
                "Set the OPENAI_API_KEY environment variable before starting the application."
            )
        # Disable SDK retries because this adapter already implements controlled backoff.
        self._client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
        self._classify_model: str = settings.OPENAI_MODEL_CLASSIFY
        self._extract_model: str = settings.OPENAI_MODEL_EXTRACT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[DocumentType, float]:
        """Classify a document and return its type with a confidence score.

        For image files (JPEG / PNG), uses GPT-4o vision with a base64-encoded
        inline image.  For PDFs, extracts readable text from the binary payload
        and sends it as a text prompt.

        Args:
            file_bytes: Raw binary content of the document.
            filename: Original filename (provides context for the model).
            content_type: MIME type (``"application/pdf"``, ``"image/jpeg"``,
                or ``"image/png"``).

        Returns:
            A tuple of ``(DocumentType, confidence)`` where confidence is 0–1.

        Raises:
            AIServiceError: If the AI provider call fails after all retries.
        """
        messages = self._build_classify_messages(file_bytes, filename, content_type)
        raw = self._call_with_retry(
            model=self._classify_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return self._parse_classify_response(raw)

    def extract_invoice_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InvoiceData:
        """Extract structured invoice data from a document.

        Args:
            file_bytes: Raw binary content of the document.
            filename: Original filename.
            content_type: MIME type.

        Returns:
            Fully populated InvoiceData instance.

        Raises:
            AIServiceError: If extraction fails after all retries.
        """
        messages = self._build_extract_messages(
            file_bytes, filename, content_type, _INVOICE_SYSTEM_PROMPT
        )
        raw = self._call_with_retry(
            model=self._extract_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return self._parse_invoice_response(raw)

    def extract_info_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InformationData:
        """Extract structured information data from a document.

        Args:
            file_bytes: Raw binary content of the document.
            filename: Original filename.
            content_type: MIME type.

        Returns:
            Fully populated InformationData instance.

        Raises:
            AIServiceError: If extraction fails after all retries.
        """
        messages = self._build_extract_messages(
            file_bytes, filename, content_type, _INFO_SYSTEM_PROMPT
        )
        raw = self._call_with_retry(
            model=self._extract_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return self._parse_info_response(raw)

    # ------------------------------------------------------------------
    # Message builders
    # ------------------------------------------------------------------

    def _build_classify_messages(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> list[dict]:
        """Build the messages list for a classification request.

        Args:
            file_bytes: Raw file content.
            filename: Original filename.
            content_type: MIME type of the file.

        Returns:
            A list of OpenAI chat message dicts.
        """
        system_msg = {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT}
        user_content = self._build_user_content(
            file_bytes,
            filename,
            content_type,
            task_instruction="Classify this document type.",
        )
        return [system_msg, {"role": "user", "content": user_content}]

    def _build_extract_messages(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        system_prompt: str,
    ) -> list[dict]:
        """Build the messages list for an extraction request.

        Args:
            file_bytes: Raw file content.
            filename: Original filename.
            content_type: MIME type of the file.
            system_prompt: Task-specific system instruction.

        Returns:
            A list of OpenAI chat message dicts.
        """
        system_msg = {"role": "system", "content": system_prompt}
        user_content = self._build_user_content(
            file_bytes,
            filename,
            content_type,
            task_instruction=(
                "Extract all visible fields from this document according to the JSON schema. "
                "Do not leave values empty when they are clearly visible."
            ),
        )
        return [system_msg, {"role": "user", "content": user_content}]

    def _build_user_content(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        task_instruction: str,
    ) -> str | list[dict]:
        """Build the user message content depending on file type.

        For images, returns a multipart vision payload with a base64-encoded
        inline image.  For PDFs, returns a plain text string with extracted
        content.

        Args:
            file_bytes: Raw file content.
            filename: Original filename.
            content_type: MIME type of the file.

        Returns:
            A string (PDF/text) or list of content parts (image vision).
        """
        if content_type in ("image/jpeg", "image/png"):
            media_type = content_type
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
            return [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{b64_data}",
                        "detail": "high",
                    },
                },
                {
                    "type": "text",
                    "text": f"Filename: {filename}. {task_instruction}",
                },
            ]

        # PDF — extract readable text from binary payload
        extracted_text = self._extract_pdf_text(file_bytes)
        if extracted_text:
            return (
                f"Filename: {filename}\n\n"
                f"Task: {task_instruction}\n\n"
                f"Extracted document text:\n{extracted_text}"
            )
        return (
            f"Filename: {filename}\n\n"
            f"Task: {task_instruction}\n\n"
            "Note: this is a PDF document. Use any available textual/visual context."
        )

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_classify_response(raw: str) -> tuple[DocumentType, float]:
        """Parse the JSON classification response into a typed tuple.

        Args:
            raw: Raw JSON string from the model.

        Returns:
            Tuple of (DocumentType, confidence float).

        Raises:
            AIServiceError: If the response cannot be parsed or is invalid.
        """
        try:
            data: dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIServiceError(
                f"Classification response is not valid JSON: {raw!r}"
            ) from exc

        type_str = str(data.get("type", "")).lower()
        confidence = float(data.get("confidence", 0.5))

        if type_str == "invoice":
            return DocumentType.INVOICE, confidence
        if type_str == "information":
            return DocumentType.INFORMATION, confidence
        return DocumentType.UNKNOWN, confidence

    @staticmethod
    def _parse_invoice_response(raw: str) -> InvoiceData:
        """Parse the JSON invoice-extraction response into an InvoiceData instance.

        Args:
            raw: Raw JSON string from the model.

        Returns:
            Fully populated InvoiceData.

        Raises:
            AIServiceError: If the response cannot be parsed.
        """
        try:
            data: dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIServiceError(
                f"Invoice extraction response is not valid JSON: {raw!r}"
            ) from exc

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
        """Parse the JSON info-extraction response into an InformationData instance.

        Args:
            raw: Raw JSON string from the model.

        Returns:
            Fully populated InformationData.

        Raises:
            AIServiceError: If the response cannot be parsed.
        """
        try:
            data: dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIServiceError(
                f"Info extraction response is not valid JSON: {raw!r}"
            ) from exc

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

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    def _call_with_retry(self, **kwargs: Any) -> str:
        """Call the OpenAI chat completions API with exponential-backoff retry.

        Retries up to ``_MAX_RETRIES`` times on RateLimitError, sleeping
        ``_RETRY_DELAYS[attempt]`` seconds between each attempt.  Other API
        errors are wrapped immediately as AIServiceError.

        Args:
            **kwargs: Keyword arguments forwarded to
                ``client.chat.completions.create``.

        Returns:
            The content string from the first successful response.

        Raises:
            AIServiceError: If all retry attempts are exhausted, or on
                authentication / connection errors.
        """
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except openai.RateLimitError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAYS[attempt])
            except openai.AuthenticationError as exc:
                raise AIServiceError(
                    f"OpenAI authentication failed — check OPENAI_API_KEY: {exc}"
                ) from exc
            except openai.APIConnectionError as exc:
                raise AIServiceError(
                    f"OpenAI connection error: {exc}"
                ) from exc
            except openai.APIError as exc:
                raise AIServiceError(f"OpenAI API error: {exc}") from exc

        raise AIServiceError(
            f"OpenAI rate limit exceeded after {_MAX_RETRIES} retries: {last_exc}"
        ) from last_exc

    # ------------------------------------------------------------------
    # PDF text extraction (no external library required)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_pdf_text(file_bytes: bytes) -> str:
        """Attempt lightweight text extraction from a PDF binary payload.

        Scans for PDF text operators (``Tj`` / ``TJ``) without requiring an
        external library.  Falls back to a printable-ASCII filter if no
        structured text blocks are found.

        Args:
            file_bytes: Raw PDF bytes.

        Returns:
            A string of extracted readable text, or an empty string if
            no text could be recovered.
        """
        texts: list[str] = []

        # Match PDF text-show operators:  (text)Tj  or  (text) TJ
        for match in re.finditer(rb"\(([^()]{1,300})\)\s*T[jJ]", file_bytes):
            try:
                fragment = match.group(1).decode("latin-1", errors="ignore").strip()
                if len(fragment) > 2:
                    texts.append(fragment)
            except Exception:
                continue

        if texts:
            # Limit to first 300 fragments to avoid sending huge prompts
            return " ".join(texts[:300])

        # Fallback: decode bytes as latin-1, keep only printable ASCII characters
        try:
            raw = file_bytes.decode("latin-1", errors="ignore")
            readable = re.sub(r"[^\x20-\x7E\n\r\t]", " ", raw)
            readable = re.sub(r"\s+", " ", readable).strip()
            words = [w for w in readable.split() if len(w) > 3]
            return " ".join(words[:500])
        except Exception:
            return ""
