"""Port: ICSVRepository — abstract CSV upload persistence interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from ..models.csv_upload import CSVRow, CSVUpload


class ICSVRepository(ABC):
    """Abstract repository for CSV upload and row persistence."""

    @abstractmethod
    def save_upload(self, upload: CSVUpload) -> CSVUpload:
        """Persist a new CSVUpload record and return the saved entity.

        Args:
            upload: Fully populated CSVUpload to persist (rows excluded).

        Returns:
            The persisted CSVUpload entity.
        """
        ...

    @abstractmethod
    def save_rows(self, rows: list[CSVRow]) -> None:
        """Bulk-insert CSV row records.

        Args:
            rows: List of CSVRow entities to persist.  Each row's ``id``
                  field will be populated by the DB after insertion.
        """
        ...

    @abstractmethod
    def update_upload_status(
        self,
        upload_id: UUID,
        status: str,
        row_count: int,
        error_count: int,
    ) -> None:
        """Update the status and row-count fields of an existing upload.

        Args:
            upload_id: UUID of the CSVUpload to update.
            status: New processing status (``"completed"`` or ``"failed"``).
            row_count: Total number of rows processed.
            error_count: Number of rows that contained validation errors.
        """
        ...

    @abstractmethod
    def get_upload_by_id(self, upload_id: UUID) -> CSVUpload | None:
        """Retrieve a CSVUpload by its primary key.

        Args:
            upload_id: UUID to look up.

        Returns:
            Matching CSVUpload entity, or ``None`` if not found.
        """
        ...
