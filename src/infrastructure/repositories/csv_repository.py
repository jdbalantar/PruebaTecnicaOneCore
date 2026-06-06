"""SQLAlchemy implementation of ICSVRepository."""

import json
from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.models.csv_upload import CSVRow, CSVUpload, ValidationError
from src.domain.ports.csv_repository import ICSVRepository
from src.infrastructure.db.models import CSVRowModel, CSVUploadModel


class CSVRepository(ICSVRepository):
    """Concrete SQLAlchemy-backed repository for CSV upload and row persistence.

    Args:
        session: An active SQLAlchemy Session scoped to the current request.
    """

    def __init__(self, session: Session) -> None:
        """Initialise the repository with a database session.

        Args:
            session: SQLAlchemy Session for executing queries.
        """
        self._session = session

    def save_upload(self, upload: CSVUpload) -> CSVUpload:
        """Persist a new CSVUpload record.

        Serialises ``validation_mode`` and ``allow_duplicates`` into the
        ``params_json`` string column.

        Args:
            upload: CSVUpload domain entity to persist (rows excluded).

        Returns:
            The persisted CSVUpload with any DB-assigned defaults populated.
        """
        params = json.dumps(
            {
                "validation_mode": upload.validation_mode,
                "allow_duplicates": upload.allow_duplicates,
            }
        )
        model = CSVUploadModel(
            id=upload.id,
            user_id=upload.user_id,
            filename=upload.filename,
            s3_key=upload.s3_key,
            s3_bucket=upload.s3_bucket,
            total_rows=0,
            valid_rows=0,
            params_json=params,
            status=upload.status,
            created_at=upload.created_at,
            updated_at=upload.updated_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._upload_to_domain(model)

    def save_rows(self, rows: list[CSVRow]) -> None:
        """Bulk-insert CSV row records.

        Serialises ``validation_errors`` as a JSON-compatible list of dicts
        for storage in the JSON column.

        Args:
            rows: List of CSVRow entities to persist.  Each row's ``id``
                  field is populated by the DB after insertion.
        """
        orm_rows = [
            CSVRowModel(
                upload_id=row.upload_id,
                row_number=row.row_number,
                row_data=row.row_data,
                validation_errors=(
                    [
                        {
                            "row_number": e.row_number,
                            "column": e.column,
                            "error_type": e.error_type,
                            "message": e.message,
                        }
                        for e in row.validation_errors
                    ]
                    if row.validation_errors
                    else None
                ),
            )
            for row in rows
        ]
        self._session.add_all(orm_rows)
        self._session.commit()

    def update_upload_status(
        self,
        upload_id: UUID,
        status: str,
        row_count: int,
        error_count: int,
    ) -> None:
        """Update status and row-count fields on an existing CSVUpload record.

        ``total_rows`` is set to ``row_count`` and ``valid_rows`` is set to
        ``row_count - error_count``.

        Args:
            upload_id: UUID of the record to update.
            status: New processing status (``"completed"`` or ``"failed"``).
            row_count: Total number of rows processed.
            error_count: Number of rows that failed validation.
        """
        model = self._session.get(CSVUploadModel, upload_id)
        if model is None:
            return
        model.status = status
        model.total_rows = row_count
        model.valid_rows = max(0, row_count - error_count)
        self._session.commit()

    def get_upload_by_id(self, upload_id: UUID) -> CSVUpload | None:
        """Retrieve a CSVUpload record by primary key.

        Args:
            upload_id: UUID to look up.

        Returns:
            Matching CSVUpload domain entity, or None if not found.
        """
        model = self._session.get(CSVUploadModel, upload_id)
        if model is None:
            return None
        return self._upload_to_domain(model)

    def _upload_to_domain(self, model: CSVUploadModel) -> CSVUpload:
        """Map a CSVUploadModel ORM instance to a CSVUpload domain entity.

        Deserialises ``params_json`` to recover ``validation_mode`` and
        ``allow_duplicates``.  Row data is not loaded (``rows`` stays empty).

        Args:
            model: The ORM model instance to map.

        Returns:
            A CSVUpload domain dataclass (rows list will be empty).
        """
        params: dict = json.loads(model.params_json) if model.params_json else {}
        return CSVUpload(
            id=model.id,
            user_id=model.user_id,
            filename=model.filename,
            s3_key=model.s3_key,
            s3_bucket=model.s3_bucket,
            validation_mode=params.get("validation_mode", "strict"),
            allow_duplicates=bool(params.get("allow_duplicates", False)),
            status=model.status,
            rows=[],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
