"""Ollama implementation of IDocumentAIPort for local, no-cost inference."""

import base64
import io
import json
import re
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

_INVOICE_FROM_TEXT_PROMPT = (
    "You are a data extraction assistant. Using the OCR text provided by the user, "
    "extract structured invoice data and respond ONLY with valid JSON matching this schema exactly: "
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

_MAX_RETRIES = 2
_RETRY_DELAYS = [1, 2]
_MONEY_CAPTURE_PATTERN = r"(\d[\d\.\s]*[\.,]\d{2})"


class OllamaDocumentAdapter(IDocumentAIPort):
    """Local Ollama adapter for classification and extraction."""

    def __init__(self, settings) -> None:
        self._base_url: str = settings.OLLAMA_BASE_URL.rstrip("/")
        self._classify_model: str = settings.OLLAMA_MODEL_CLASSIFY
        self._extract_model: str = settings.OLLAMA_MODEL_EXTRACT
        self._request_timeout_seconds: float = float(settings.OLLAMA_REQUEST_TIMEOUT_SECONDS)
        self._ocr_text_max_chars: int = settings.OLLAMA_OCR_TEXT_MAX_CHARS
        self._ocr_enabled: bool = settings.OCR_ENABLED
        self._ocr_lang: str = settings.OCR_LANG
        self._ocr_tesseract_cmd: str | None = settings.OCR_TESSERACT_CMD
        self._ocr_pdf_max_pages: int = settings.OCR_PDF_MAX_PAGES
        self._ocr_min_text_chars: int = settings.OCR_MIN_TEXT_CHARS

    def classify_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[DocumentType, float]:
        raw = self._run_chat(
            model=self._classify_model,
            instruction=_CLASSIFY_SYSTEM_PROMPT,
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            user_task="Classify this document and return only the JSON schema requested.",
        )
        return self._parse_classify_response(raw)

    def extract_invoice_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InvoiceData:
        cleaned_source_text = self._clean_transcribed_text(
            self._extract_text_with_ocr(file_bytes, content_type)
        )

        parsed = self._empty_invoice_data()
        parsed_from_text = self._empty_invoice_data()

        # Prefer OCR->text extraction path first to avoid slow vision generations.
        if cleaned_source_text:
            try:
                structured_from_text_raw = self._run_text_to_json_chat(
                    model=self._extract_model,
                    instruction=_INVOICE_FROM_TEXT_PROMPT,
                    text_payload=cleaned_source_text,
                    user_task="Extract invoice fields from this OCR text.",
                )
                parsed_from_text = self._parse_invoice_response(structured_from_text_raw)
                parsed_from_text = self._sanitize_invoice_with_source_text(
                    parsed_from_text,
                    cleaned_source_text,
                )
            except AIServiceError:
                # Keep deterministic OCR heuristics as fallback even if the model times out.
                parsed_from_text = self._empty_invoice_data()
        else:
            raw = self._run_chat(
                model=self._extract_model,
                instruction=_INVOICE_SYSTEM_PROMPT,
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                user_task=(
                    "Extract all visible invoice fields. "
                    "Do not keep empty strings or zeros when values are visible in the document."
                ),
            )
            parsed = self._parse_invoice_response(raw)

        parsed = self._sanitize_invoice_with_source_text(parsed, cleaned_source_text)
        heuristics = self._heuristic_invoice_from_text(cleaned_source_text)
        return self._merge_invoice_data_with_source_priority(
            primary=parsed,
            text_based=parsed_from_text,
            heuristic=heuristics,
        )

    def extract_info_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InformationData:
        raw = self._run_chat(
            model=self._extract_model,
            instruction=_INFO_SYSTEM_PROMPT,
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            user_task=(
                "Extract description, summary, and sentiment from the visible content. "
                "Return only valid JSON."
            ),
        )
        return self._parse_info_response(raw)

    def _run_chat(
        self,
        model: str,
        instruction: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        user_task: str,
        force_json: bool = True,
    ) -> str:
        endpoint = f"{self._base_url}/api/chat"
        messages = [
            {"role": "system", "content": instruction},
            self._build_user_message(file_bytes, filename, content_type, user_task),
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if force_json:
            payload["format"] = "json"

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = httpx.post(
                    endpoint,
                    json=payload,
                    timeout=self._request_timeout_seconds,
                )
                response.raise_for_status()

                body = response.json()
                message = body.get("message") or {}
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise AIServiceError(f"Ollama returned empty content: {body}")
                return content
            except (httpx.HTTPError, httpx.TimeoutException, AIServiceError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAYS[attempt])
                    continue
                break

        raise AIServiceError(
            f"Ollama request failed after {_MAX_RETRIES} retries: {last_exc}"
        ) from last_exc

    def _run_text_to_json_chat(
        self,
        model: str,
        instruction: str,
        text_payload: str,
        user_task: str,
    ) -> str:
        endpoint = f"{self._base_url}/api/chat"
        messages = [
            {"role": "system", "content": instruction},
            {
                "role": "user",
                "content": (
                    f"Task: {user_task}\n\n"
                    "OCR source text (verbatim):\n"
                    f"{self._truncate_text(text_payload)}"
                ),
            },
        ]

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = httpx.post(
                    endpoint,
                    json=payload,
                    timeout=self._request_timeout_seconds,
                )
                response.raise_for_status()

                body = response.json()
                message = body.get("message") or {}
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise AIServiceError(
                        f"Ollama text->json returned empty content: {body}"
                    )
                return content
            except (httpx.HTTPError, httpx.TimeoutException, AIServiceError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAYS[attempt])
                    continue
                break

        raise AIServiceError(
            f"Ollama text->json request failed after {_MAX_RETRIES} retries: {last_exc}"
        ) from last_exc

    def _build_user_message(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        user_task: str,
    ) -> dict[str, Any]:
        ocr_text = self._extract_text_with_ocr(file_bytes, content_type)

        if content_type in ("image/jpeg", "image/png"):
            content = f"Filename: {filename}. Task: {user_task}"
            if ocr_text:
                content = (
                    f"{content}\n\n"
                    "OCR extracted text (use this as primary evidence; do not invent values):\n"
                    f"{self._truncate_text(ocr_text)}"
                )
            return {
                "role": "user",
                "content": content,
                "images": [base64.b64encode(file_bytes).decode("utf-8")],
            }

        extracted_text = self._extract_pdf_text(file_bytes)
        combined_text = self._merge_text_sources(extracted_text, ocr_text)
        content = (
            f"Filename: {filename}. Task: {user_task}\n\n"
            f"Extracted document text:\n{combined_text}"
            if combined_text
            else f"Filename: {filename}. Task: {user_task}"
        )
        return {"role": "user", "content": content}

    def _extract_text_with_ocr(self, file_bytes: bytes, content_type: str) -> str:
        if not self._ocr_enabled:
            return ""

        if content_type in ("image/jpeg", "image/png"):
            return self._ocr_image(file_bytes)

        if content_type != "application/pdf":
            return ""

        embedded_text = self._extract_pdf_text(file_bytes)
        if len(embedded_text.strip()) >= self._ocr_min_text_chars:
            return embedded_text

        return self._ocr_pdf(file_bytes)

    @staticmethod
    def _merge_text_sources(primary_text: str, secondary_text: str) -> str:
        if primary_text and secondary_text:
            if OllamaDocumentAdapter._normalize_text(secondary_text) in OllamaDocumentAdapter._normalize_text(
                primary_text
            ):
                return primary_text
            return f"{primary_text}\n\n{secondary_text}"
        return primary_text or secondary_text

    def _configure_tesseract_path(self, pytesseract_module) -> None:
        if self._ocr_tesseract_cmd:
            pytesseract_module.pytesseract.tesseract_cmd = self._ocr_tesseract_cmd

    def _ocr_image(self, file_bytes: bytes) -> str:
        try:
            from PIL import Image
            import pytesseract
        except Exception:
            return ""

        self._configure_tesseract_path(pytesseract)
        try:
            image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            text = pytesseract.image_to_string(image, lang=self._ocr_lang)
            return text.strip()
        except Exception:
            return ""

    def _ocr_pdf(self, file_bytes: bytes) -> str:
        try:
            import pypdfium2 as pdfium
            import pytesseract
        except Exception:
            return ""

        self._configure_tesseract_path(pytesseract)
        ocr_chunks: list[str] = []

        try:
            document = pdfium.PdfDocument(file_bytes)
        except Exception:
            return ""

        try:
            page_count = len(document)
            max_pages = min(max(1, self._ocr_pdf_max_pages), page_count)
            for page_index in range(max_pages):
                page = document[page_index]
                try:
                    bitmap = page.render(scale=2)
                    pil_image = bitmap.to_pil().convert("RGB")
                    text = pytesseract.image_to_string(pil_image, lang=self._ocr_lang).strip()
                    if text:
                        ocr_chunks.append(text)
                except Exception:
                    continue
                finally:
                    page.close()
        finally:
            document.close()

        return "\n".join(ocr_chunks).strip()

    def _truncate_text(self, value: str) -> str:
        if len(value) <= self._ocr_text_max_chars:
            return value
        return value[: self._ocr_text_max_chars]

    @staticmethod
    def _parse_classify_response(raw: str) -> tuple[DocumentType, float]:
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

    @staticmethod
    def _empty_invoice_data() -> InvoiceData:
        return InvoiceData(
            client_name="",
            client_address="",
            supplier_name="",
            supplier_address="",
            invoice_number="",
            date="",
            products=[],
            total=0.0,
        )

    @staticmethod
    def _is_invoice_data_effectively_empty(data: InvoiceData) -> bool:
        if data.client_name.strip() or data.client_address.strip():
            return False
        if data.supplier_name.strip() or data.supplier_address.strip():
            return False
        if data.invoice_number.strip() or data.date.strip():
            return False
        if data.total and data.total > 0:
            return False

        meaningful_products = [
            p
            for p in data.products
            if p.name.strip() or p.quantity > 0 or p.unit_price > 0 or p.total > 0
        ]
        return len(meaningful_products) == 0

    @staticmethod
    def _extract_pdf_text(file_bytes: bytes) -> str:
        texts: list[str] = []
        for match in re.finditer(rb"\(([^()]{1,300})\)\s*T[jJ]", file_bytes):
            try:
                fragment = match.group(1).decode("latin-1", errors="ignore").strip()
                if len(fragment) > 2:
                    texts.append(fragment)
            except Exception:
                continue

        if texts:
            return " ".join(texts[:300])

        try:
            raw = file_bytes.decode("latin-1", errors="ignore")
            readable = re.sub(r"[^\x20-\x7E\n\r\t]", " ", raw)
            readable = re.sub(r"\s+", " ", readable).strip()
            words = [w for w in readable.split() if len(w) > 3]
            return " ".join(words[:500])
        except Exception:
            return ""

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = value.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.replace("á", "a").replace("é", "e")
        normalized = normalized.replace("í", "i").replace("ó", "o").replace("ú", "u")
        normalized = normalized.replace("ñ", "n")
        return normalized

    def _is_value_in_source(self, source: str, value: str) -> bool:
        if not value.strip():
            return False
        return self._normalize_text(value) in self._normalize_text(source)

    def _sanitize_invoice_with_source_text(self, data: InvoiceData, source_text: str) -> InvoiceData:
        client_name = data.client_name if self._is_field_value_valid(source_text, data.client_name) else ""
        client_address = (
            data.client_address if self._is_field_value_valid(source_text, data.client_address) else ""
        )
        supplier_name = (
            data.supplier_name if self._is_field_value_valid(source_text, data.supplier_name) else ""
        )
        supplier_address = (
            data.supplier_address
            if self._is_field_value_valid(source_text, data.supplier_address)
            else ""
        )
        invoice_number = self._sanitize_invoice_number(source_text, data.invoice_number)
        date = self._sanitize_date(source_text, data.date)

        sanitized_products: list[InvoiceProduct] = []
        for item in data.products:
            keep_name = self._is_field_value_valid(source_text, item.name)
            # Do not keep product rows without a source-anchored name.
            if keep_name:
                sanitized_products.append(
                    InvoiceProduct(
                        quantity=item.quantity,
                        name=item.name if keep_name else "",
                        unit_price=item.unit_price,
                        total=item.total,
                    )
                )

        anchored_total = self._extract_total_from_text(source_text)
        total = anchored_total if anchored_total > 0 else 0.0

        return InvoiceData(
            client_name=client_name,
            client_address=client_address,
            supplier_name=supplier_name,
            supplier_address=supplier_address,
            invoice_number=invoice_number,
            date=date,
            products=sanitized_products,
            total=total,
        )

    @staticmethod
    def _find_after_label(source_text: str, label_pattern: str) -> str:
        pattern = re.compile(label_pattern, re.IGNORECASE)
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if pattern.search(line):
                # Same-line value after colon/label.
                same_line = re.sub(label_pattern, "", line, flags=re.IGNORECASE).strip(" :-")
                if same_line and not OllamaDocumentAdapter._looks_like_meta_text(same_line):
                    return same_line
                # Next non-empty line often carries the value.
                if idx + 1 < len(lines):
                    candidate = lines[idx + 1].strip()
                    if not OllamaDocumentAdapter._looks_like_meta_text(candidate):
                        return candidate
        return ""

    def _heuristic_invoice_from_text(self, source_text: str) -> InvoiceData:
        # Common Spanish labels in this invoice template.
        invoice_number = self._extract_invoice_number_from_text(source_text)
        date = self._extract_date_from_text(source_text)
        total = self._extract_total_from_text(source_text)
        supplier_name = self._extract_supplier_name(source_text)
        supplier_address = self._extract_address_after_label(source_text, r"^de\b")

        client_name = self._find_after_label(source_text, r"^para\b")
        if not client_name:
            client_name = self._find_after_label(source_text, r"facturar\W*a")
        if not client_name:
            client_name = self._find_after_label(source_text, r"enviar\W*a")
        if not client_name:
            client_name = self._find_after_label(source_text, r"bill\W*to")
        if not client_name:
            client_name = self._find_after_label(source_text, r"ship\W*to")
        client_address = self._extract_address_after_label(source_text, r"^para\b")

        products = self._extract_products_from_text(source_text)

        return InvoiceData(
            client_name=client_name,
            client_address=client_address,
            supplier_name=supplier_name,
            supplier_address=supplier_address,
            invoice_number=invoice_number,
            date=date,
            products=products,
            total=total,
        )

    @staticmethod
    def _merge_invoice_data(primary: InvoiceData, fallback: InvoiceData) -> InvoiceData:
        return InvoiceData(
            client_name=primary.client_name or fallback.client_name,
            client_address=primary.client_address or fallback.client_address,
            supplier_name=primary.supplier_name or fallback.supplier_name,
            supplier_address=primary.supplier_address or fallback.supplier_address,
            invoice_number=primary.invoice_number or fallback.invoice_number,
            date=primary.date or fallback.date,
            products=primary.products if primary.products else fallback.products,
            total=primary.total if primary.total > 0 else fallback.total,
        )

    @staticmethod
    def _parse_decimal(raw: str) -> float:
        candidate = raw.strip().replace(" ", "")
        # Handle common formats: 1.234,56 | 1,234.56 | 1234,56 | 1234.56
        if "," in candidate and "." in candidate:
            if candidate.rfind(",") > candidate.rfind("."):
                candidate = candidate.replace(".", "").replace(",", ".")
            else:
                candidate = candidate.replace(",", "")
        else:
            candidate = candidate.replace(",", ".")
        try:
            return float(candidate)
        except ValueError:
            return 0.0

    @staticmethod
    def _clean_invoice_number(value: str) -> str:
        return re.sub(r"[^\w\-/]", "", value or "").strip()

    @staticmethod
    def _normalize_date(value: str) -> str:
        candidate = (value or "").strip()
        if not candidate:
            return ""

        iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", candidate)
        if iso:
            return candidate

        dmy = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", candidate)
        if dmy:
            day = int(dmy.group(1))
            month = int(dmy.group(2))
            year = int(dmy.group(3))
            if year < 100:
                year += 2000
            if 1 <= day <= 31 and 1 <= month <= 12:
                return f"{year:04d}-{month:02d}-{day:02d}"

        return ""

    def _merge_invoice_data_with_source_priority(
        self,
        primary: InvoiceData,
        text_based: InvoiceData,
        heuristic: InvoiceData,
    ) -> InvoiceData:
        # Prefer OCR-derived deterministic fields first, then model outputs.
        if heuristic.products:
            merged_products = heuristic.products
        elif text_based.products:
            merged_products = text_based.products
        else:
            merged_products = primary.products

        if heuristic.total > 0:
            merged_total = heuristic.total
        elif text_based.total > 0:
            merged_total = text_based.total
        else:
            merged_total = 0.0

        return InvoiceData(
            client_name=heuristic.client_name or text_based.client_name or primary.client_name,
            client_address=text_based.client_address or primary.client_address,
            supplier_name=heuristic.supplier_name or text_based.supplier_name or primary.supplier_name,
            supplier_address=text_based.supplier_address or primary.supplier_address,
            invoice_number=(
                heuristic.invoice_number or text_based.invoice_number or primary.invoice_number
            ),
            date=heuristic.date or text_based.date or primary.date,
            products=merged_products,
            total=merged_total,
        )

    def _extract_date_from_text(self, source_text: str) -> str:
        for label in (r"invoice\W*date", r"fecha\W*de\W*factura", r"^fecha"):
            date = self._normalize_date(self._find_after_label(source_text, label))
            if date:
                return date

        any_date_match = re.search(
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b",
            source_text,
        )
        if not any_date_match:
            return ""
        return self._normalize_date(any_date_match.group(1))

    def _extract_total_from_text(self, source_text: str) -> float:
        # Prefer explicit TOTAL line and avoid matching SUBTOTAL.
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        for line in reversed(lines):
            normalized = self._normalize_text(line)
            if not normalized.startswith("total"):
                continue
            if normalized.startswith("subtotal"):
                continue

            amount_match = re.search(_MONEY_CAPTURE_PATTERN, line)
            if amount_match:
                return self._parse_decimal(amount_match.group(1))

        # Fallback for OCR where TOTAL may not be at line start.
        for line in reversed(lines):
            normalized = self._normalize_text(line)
            if "total" not in normalized or "subtotal" in normalized:
                continue

            amount_match = re.search(_MONEY_CAPTURE_PATTERN, line)
            if amount_match:
                return self._parse_decimal(amount_match.group(1))

        # Last-resort fallback: use the largest monetary amount found in the document.
        amounts = re.findall(_MONEY_CAPTURE_PATTERN, source_text)
        parsed_amounts = [self._parse_decimal(value) for value in amounts]
        parsed_amounts = [value for value in parsed_amounts if value > 0]
        if parsed_amounts:
            return max(parsed_amounts)

        return 0.0

    def _extract_supplier_name(self, source_text: str) -> str:
        from_de = self._extract_party_name_from_block(source_text, r"^de\b")
        if from_de:
            return from_de

        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        if not lines:
            return ""

        for line in lines:
            if self._looks_like_meta_text(line):
                continue
            normalized_line = self._normalize_text(line)
            if any(
                token in normalized_line
                for token in (
                    "factura",
                    "facturar a",
                    "enviar a",
                    "bill to",
                    "ship to",
                    "invoice date",
                    "invoice #",
                )
            ):
                continue
            if re.search(r"inc\.?$", line, flags=re.IGNORECASE):
                return line

        return self._first_plausible_party_line(lines)

    def _extract_products_from_text(self, source_text: str) -> list[InvoiceProduct]:
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        products: list[InvoiceProduct] = []
        products.extend(self._extract_products_pattern_quantity_first(source_text))
        products.extend(self._extract_products_pattern_three_amounts(lines))
        products.extend(self._extract_products_pattern_currency_ocr(lines))

        return self._dedupe_products(products)

    def _extract_invoice_number_from_text(self, source_text: str) -> str:
        for label in (r"^numero\s+de\s+factura", r"^numero(?!\s+de\s+pedido)\b", r"invoice\W*#"):
            candidate = self._clean_invoice_number(self._find_after_label(source_text, label))
            if candidate:
                return candidate

        inline = re.search(
            r"(?im)\b(?:numero(?:\s+de\s+factura)?|invoice\s*#)\b\s*[:\-]?\s*([A-Z0-9\-/]{2,})",
            source_text,
        )
        if inline:
            return self._clean_invoice_number(inline.group(1))
        return ""

    def _extract_address_after_label(self, source_text: str, label_pattern: str) -> str:
        pattern = re.compile(label_pattern, re.IGNORECASE)
        stop_pattern = re.compile(
            r"^(de|para|numero|fecha|descripcion|cantidad|precio|importe|subtotal|descuento|iva|total)\b",
            re.IGNORECASE,
        )
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if not pattern.search(line):
                continue

            collected: list[str] = []
            for next_line in lines[idx + 1 : idx + 5]:
                if stop_pattern.search(next_line):
                    break
                if self._looks_like_meta_text(next_line) or self._looks_like_section_label(next_line):
                    continue
                if re.fullmatch(r"\d+[\.,]\d{2}\s*€?", next_line):
                    break
                collected.append(next_line)

            return ", ".join(collected)

        return ""

    def _extract_party_name_from_block(self, source_text: str, label_pattern: str) -> str:
        pattern = re.compile(label_pattern, re.IGNORECASE)
        stop_pattern = re.compile(
            r"^(de|para|numero|fecha|descripcion|cantidad|precio|importe|subtotal|descuento|iva|total)\b",
            re.IGNORECASE,
        )
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if not pattern.search(line):
                continue

            for next_line in lines[idx + 1 : idx + 4]:
                if stop_pattern.search(next_line):
                    break
                if self._looks_like_meta_text(next_line) or self._looks_like_section_label(next_line):
                    continue
                if not self._is_plausible_party_name(next_line):
                    continue
                return next_line

        return ""

    def _is_plausible_party_name(self, value: str) -> bool:
        stripped = value.strip()
        if len(stripped) < 4:
            return False
        if re.fullmatch(r"[\W\d_]+", stripped):
            return False
        alpha_count = sum(1 for ch in stripped if ch.isalpha())
        if alpha_count < 3:
            return False
        vowels = sum(1 for ch in stripped.lower() if ch in "aeiouáéíóú")
        return vowels >= 2

    def _first_plausible_party_line(self, lines: list[str]) -> str:
        for line in lines:
            if self._looks_like_meta_text(line) or self._looks_like_section_label(line):
                continue
            if not self._is_plausible_party_name(line):
                continue
            return line
        return ""

    def _extract_products_pattern_quantity_first(self, source_text: str) -> list[InvoiceProduct]:
        products: list[InvoiceProduct] = []
        for match in re.finditer(
            r"\b(\d+)\s+(.+?)\s+(\d+[\.,]\d{2})\s+(\d+[\.,]\d{2})\b",
            source_text,
            flags=re.IGNORECASE,
        ):
            products.append(
                InvoiceProduct(
                    quantity=float(match.group(1)),
                    name=match.group(2).strip(),
                    unit_price=self._parse_decimal(match.group(3)),
                    total=self._parse_decimal(match.group(4)),
                )
            )
        return products

    def _extract_products_pattern_three_amounts(self, lines: list[str]) -> list[InvoiceProduct]:
        products: list[InvoiceProduct] = []
        for line in lines:
            if self._is_summary_line(line):
                continue

            match = re.search(
                r"(.+?)\s+(\d+[\.,]\d{2})\s+(\d+[\.,]\d{2})\s+(\d+[\.,]\d{2})\s*$",
                line,
            )
            if not match:
                continue

            description = match.group(1).strip()
            if self._looks_like_section_label(description):
                continue
            if not re.search(r"[A-Za-z]", description):
                continue

            products.append(
                InvoiceProduct(
                    quantity=self._parse_decimal(match.group(2)),
                    name=description,
                    unit_price=self._parse_decimal(match.group(3)),
                    total=self._parse_decimal(match.group(4)),
                )
            )
        return products

    def _extract_products_pattern_currency_ocr(self, lines: list[str]) -> list[InvoiceProduct]:
        products: list[InvoiceProduct] = []
        for line in lines:
            if self._is_summary_line(line):
                continue

            numeric_tokens = re.findall(r"\d+[\.,]\d{2}", line)
            if len(numeric_tokens) < 3:
                continue

            description = re.split(r"\d+[\.,]\d{2}", line, maxsplit=1)[0].strip()
            if not description or self._looks_like_section_label(description):
                continue

            quantity = self._parse_decimal(numeric_tokens[0])
            unit_price = self._parse_decimal(numeric_tokens[-2])
            total = self._parse_decimal(numeric_tokens[-1])
            if quantity <= 0 or unit_price <= 0 or total <= 0:
                continue

            products.append(
                InvoiceProduct(
                    quantity=quantity,
                    name=description,
                    unit_price=unit_price,
                    total=total,
                )
            )
        return products

    def _is_summary_line(self, line: str) -> bool:
        normalized_line = self._normalize_text(line)
        return normalized_line.startswith(("subtotal", "descuento", "iva", "total"))

    def _dedupe_products(self, products: list[InvoiceProduct]) -> list[InvoiceProduct]:
        deduped: list[InvoiceProduct] = []
        seen: set[str] = set()
        for item in products:
            key = f"{self._normalize_text(item.name)}|{item.total:.2f}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _looks_like_section_label(self, value: str) -> bool:
        normalized = self._normalize_text(value)
        section_tokens = (
            "factura",
            "de",
            "para",
            "numero",
            "fecha",
            "descripcion",
            "cantidad",
            "precio unidad",
            "importe",
            "subtotal",
            "descuento",
            "iva",
            "total",
        )
        return normalized in section_tokens

    @staticmethod
    def _looks_like_meta_text(value: str) -> bool:
        normalized = OllamaDocumentAdapter._normalize_text(value)
        meta_patterns = (
            "the image shows",
            "here is the transcribed text",
            "transcribed text from",
            "ocr",
            "document appears to",
        )
        return any(pattern in normalized for pattern in meta_patterns)

    def _is_field_value_valid(self, source_text: str, value: str) -> bool:
        if not self._is_value_in_source(source_text, value):
            return False
        return not self._looks_like_meta_text(value)

    def _sanitize_invoice_number(self, source_text: str, invoice_number: str) -> str:
        cleaned = self._clean_invoice_number(invoice_number)
        if not cleaned:
            return ""
        if not self._is_field_value_valid(source_text, cleaned):
            return ""

        source = self._normalize_text(source_text)
        token = re.escape(self._normalize_text(cleaned))
        has_label_context = bool(
            re.search(rf"(invoice|factura|n\s*de\s*factura)[^\n]{{0,25}}{token}", source)
        )
        if has_label_context:
            return cleaned

        # Reject generic long digits without invoice label context (often account/routing numbers).
        if re.fullmatch(r"\d{8,}", cleaned):
            return ""
        return cleaned

    def _sanitize_date(self, source_text: str, value: str) -> str:
        normalized = self._normalize_date(value)
        if not normalized:
            return ""

        if self._is_field_value_valid(source_text, value) or self._is_field_value_valid(source_text, normalized):
            return normalized
        return ""

    def _clean_transcribed_text(self, source_text: str) -> str:
        lines = [line.rstrip() for line in source_text.splitlines()]
        kept: list[str] = []
        for line in lines:
            candidate = line.strip()
            if not candidate:
                continue
            if self._looks_like_meta_text(candidate):
                continue
            kept.append(candidate)
        return "\n".join(kept)
