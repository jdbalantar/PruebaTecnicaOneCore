"""SQLAlchemy implementation of IDocumentRepository."""

from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.models.document import (
    Document,
    DocumentType,
    InformationData,
    InvoiceData,
    InvoiceProduct,
    Sentiment,
)
from src.domain.ports.document_repository import IDocumentRepository
from src.infrastructure.db.models import DocumentModel


class DocumentRepository(IDocumentRepository):
    """Concrete SQLAlchemy-backed repository for Document persistence.

    Args:
        session: An active SQLAlchemy Session scoped to the current request.
    """

    def __init__(self, session: Session) -> None:
        """Initialise the repository with a database session.

        Args:
            session: SQLAlchemy Session for executing queries.
        """
        self._session = session

    def save(self, document: Document) -> Document:
        """Persist a new Document record.

        Derives ``file_type`` from the filename extension, serialises
        ``extracted_data`` to a plain dict for the JSON column, and maps
        ``confidence`` → ``classification_confidence``.

        Args:
            document: Fully populated Document domain entity to persist.

        Returns:
            The persisted Document with any DB-assigned defaults populated.
        """
        file_type = self._derive_file_type(document.filename)
        extracted_raw = self._serialize_extracted_data(document.extracted_data)

        model = DocumentModel(
            id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            file_type=file_type,
            s3_key=document.s3_key,
            s3_bucket=document.s3_bucket,
            doc_type=(
                document.doc_type.value
                if isinstance(document.doc_type, DocumentType)
                else document.doc_type
            ),
            classification_confidence=document.confidence,
            extracted_data=extracted_raw,
            ai_model=document.ai_model,
            created_at=document.created_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, doc_id: UUID) -> Document | None:
        """Retrieve a Document record by primary key.

        Args:
            doc_id: UUID of the document to look up.

        Returns:
            Matching Document domain entity, or None if not found.
        """
        model = self._session.get(DocumentModel, doc_id)
        if model is None:
            return None
        return self._to_domain(model)

    @staticmethod
    def _derive_file_type(filename: str) -> str:
        """Derive the ORM ``file_type`` value from a filename extension.

        Args:
            filename: Original client-provided filename.

        Returns:
            Lowercase extension without dot: ``'pdf'``, ``'jpg'``, or ``'png'``.
            Falls back to ``'pdf'`` for unrecognised extensions.
        """
        if "." not in filename:
            return "pdf"
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext if ext in ("pdf", "jpg", "png") else "pdf"

    @staticmethod
    def _serialize_extracted_data(
        data: InvoiceData | InformationData | None,
    ) -> dict | None:
        """Convert a typed extracted-data object to a plain dict for JSON storage.

        Args:
            data: InvoiceData, InformationData, or None.

        Returns:
            A dict representation suitable for the JSON column, or None.
        """
        if data is None:
            return None
        if isinstance(data, InvoiceData):
            return {
                "client_name": data.client_name,
                "client_address": data.client_address,
                "supplier_name": data.supplier_name,
                "supplier_address": data.supplier_address,
                "invoice_number": data.invoice_number,
                "date": data.date,
                "products": [
                    {
                        "quantity": p.quantity,
                        "name": p.name,
                        "unit_price": p.unit_price,
                        "total": p.total,
                    }
                    for p in data.products
                ],
                "total": data.total,
            }
        if isinstance(data, InformationData):
            return {
                "description": data.description,
                "summary": data.summary,
                "sentiment": (
                    data.sentiment.value
                    if isinstance(data.sentiment, Sentiment)
                    else data.sentiment
                ),
            }
        return None

    def _to_domain(self, model: DocumentModel) -> Document:
        """Map a DocumentModel ORM instance to a Document domain entity.

        Converts ``doc_type`` string → DocumentType enum,
        ``classification_confidence`` → ``confidence``, and deserialises
        ``extracted_data`` dict → typed InvoiceData or InformationData.

        Args:
            model: The ORM model instance to map.

        Returns:
            A Document domain dataclass.
        """
        doc_type = (
            DocumentType(model.doc_type) if model.doc_type else DocumentType.UNKNOWN
        )
        extracted = self._deserialize_extracted_data(doc_type, model.extracted_data)
        return Document(
            id=model.id,
            user_id=model.user_id,
            filename=model.filename,
            s3_key=model.s3_key,
            s3_bucket=model.s3_bucket,
            doc_type=doc_type,
            extracted_data=extracted,
            ai_model=model.ai_model,
            confidence=model.classification_confidence,
            created_at=model.created_at,
        )

    @staticmethod
    def _deserialize_extracted_data(
        doc_type: DocumentType,
        data: dict | None,
    ) -> InvoiceData | InformationData | None:
        """Convert a plain dict from JSON storage to a typed extracted-data object.

        Args:
            doc_type: Document type that determines which dataclass to build.
            data: Raw dict from the JSON column, or None.

        Returns:
            InvoiceData, InformationData, or None.
        """
        if data is None:
            return None
        if doc_type == DocumentType.INVOICE:
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
        if doc_type == DocumentType.INFORMATION:
            sentiment_raw = data.get("sentiment", "neutral")
            return InformationData(
                description=data.get("description", ""),
                summary=data.get("summary", ""),
                sentiment=Sentiment(sentiment_raw),
            )
        return None
