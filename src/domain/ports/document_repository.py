"""Port: IDocumentRepository — abstract document persistence interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from ..models.document import Document


class IDocumentRepository(ABC):
    """Abstract repository for Document persistence."""

    @abstractmethod
    def save(self, document: Document) -> Document:
        """Persist a new Document and return the saved entity.

        Args:
            document: Fully populated Document dataclass to persist.

        Returns:
            The persisted Document entity.
        """
        ...

    @abstractmethod
    def get_by_id(self, doc_id: UUID) -> Document | None:
        """Retrieve a Document by its primary key.

        Args:
            doc_id: UUID of the document to look up.

        Returns:
            Matching Document entity, or ``None`` if not found.
        """
        ...
