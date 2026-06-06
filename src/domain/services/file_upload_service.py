"""Domain service: FileUploadService — CSV validation, S3 storage, and DB persistence."""

import csv
import hashlib
import io
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ..exceptions import StorageError, ValidationError
from ..models.csv_upload import CSVRow, CSVUpload, UploadResult
from ..models.csv_upload import ValidationError as CSVValidationError
from ..models.event import Event, EventType
from ..ports.csv_repository import ICSVRepository
from ..ports.event_repository import IEventRepository
from ..ports.file_storage import IFileStoragePort


class FileUploadService:
    """Handles CSV file upload, validation, S3 storage, and DB persistence.

    Orchestrates the full CSV ingestion pipeline: size/encoding checks,
    row-level validation, S3 upload, database persistence, and audit logging.

    Args:
        csv_repo: Repository for persisting upload metadata and rows.
        storage: File-storage port for uploading raw bytes to S3.
        event_repo: Event repository for writing audit-log entries.
        settings: Application settings (provides size/row limits and bucket names).
    """

    def __init__(
        self,
        csv_repo: ICSVRepository,
        storage: IFileStoragePort,
        event_repo: IEventRepository,
        settings,
        storage_by_provider: dict[str, IFileStoragePort] | None = None,
    ) -> None:
        self._csv_repo = csv_repo
        self._storage = storage
        self._storage_by_provider = {"minio": storage}
        if storage_by_provider:
            self._storage_by_provider.update(
                {k.strip().lower(): v for k, v in storage_by_provider.items()}
            )
        self._event_repo = event_repo
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_and_validate(
        self,
        file_bytes: bytes,
        filename: str,
        validation_mode: str,
        allow_duplicates: bool,
        user_id: UUID,
        storage_provider: str | None = None,
    ) -> UploadResult:
        """Validate CSV content, upload to S3, persist rows to DB, and log events.

        Processing steps:
        1. Reject files exceeding the configured size limit.
        2. Decode the file as UTF-8 (raises on encoding errors).
        3. Parse rows with :class:`csv.DictReader`.
        4. Reject files exceeding the configured row-count limit.
        5. Validate each row: detect empty column values and duplicate rows.
        6. If ``validation_mode`` is ``"strict"`` and errors exist, raise immediately.
        7. Upload the raw file to S3 at ``csv/{user_id}/{timestamp}_{filename}``.
        8. Persist the upload record and all parsed rows to the database.
        9. Update the upload status with final row and error counts.
        10. Log ``CSV_UPLOAD`` and ``CSV_VALIDATION`` audit events.

        Args:
            file_bytes: Raw CSV file content.
            filename: Original client-provided filename.
            validation_mode: ``"strict"`` (abort on first batch of errors) or
                ``"lenient"`` (collect errors and continue).
            allow_duplicates: When ``False``, duplicate rows are flagged as errors.
            user_id: UUID of the authenticated user performing the upload.

        Returns:
            :class:`UploadResult` with total/valid/error row counts and a flat list
            of all :class:`CSVValidationError` instances found.

        Raises:
            ValidationError: If the file exceeds the size or row-count limit, is not
                UTF-8 encoded, or if ``validation_mode`` is ``"strict"`` and any
                row-level errors are detected.
            StorageError: If the S3 upload fails.
        """
        # 1. Check file size
        max_bytes = self._settings.CSV_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValidationError(
                f"File exceeds maximum allowed size of {self._settings.CSV_MAX_FILE_SIZE_MB} MB"
            )

        # 2. Decode UTF-8
        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("File must be UTF-8 encoded") from exc

        # 3. Parse CSV
        reader = csv.DictReader(io.StringIO(content))
        raw_rows = list(reader)

        # 4. Check row count limit
        if len(raw_rows) > self._settings.CSV_MAX_ROWS:
            raise ValidationError(
                f"File exceeds maximum of {self._settings.CSV_MAX_ROWS} rows"
            )

        upload_id = uuid4()
        all_validation_errors: list[CSVValidationError] = []
        csv_rows: list[CSVRow] = []
        seen_hashes: set[str] = set()

        # 5. Validate each row
        for row_number, row_dict in enumerate(raw_rows, start=1):
            row = self._validate_row(
                row_number=row_number,
                row_dict=dict(row_dict),
                upload_id=upload_id,
                allow_duplicates=allow_duplicates,
                seen_hashes=seen_hashes,
            )
            csv_rows.append(row)
            all_validation_errors.extend(row.validation_errors)

        # Strict mode: abort if any errors were found
        if validation_mode == "strict" and all_validation_errors:
            raise ValidationError(
                f"Strict validation failed: {len(all_validation_errors)} error(s) detected"
            )

        # 6. Upload raw file to S3
        selected_provider, selected_storage, bucket = self._resolve_storage_for_csv(
            storage_provider
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"csv/{user_id}/{timestamp}_{filename}"

        try:
            selected_storage.upload_file(
                file_bytes=file_bytes,
                key=s3_key,
                bucket=bucket,
                content_type="text/csv",
                metadata={"user_id": str(user_id), "filename": filename},
            )
        except Exception as exc:
            raise StorageError(f"Failed to upload CSV to S3: {exc}") from exc

        total_rows = len(csv_rows)
        error_rows = len({e.row_number for e in all_validation_errors})
        valid_rows = total_rows - error_rows
        status = "completed"

        # 7. Persist upload record
        upload = CSVUpload(
            id=upload_id,
            user_id=user_id,
            filename=filename,
            s3_key=s3_key,
            s3_bucket=bucket,
            validation_mode=validation_mode,
            allow_duplicates=allow_duplicates,
            status="uploaded",
            rows=[],
        )
        self._csv_repo.save_upload(upload)

        # 8. Persist all rows
        self._csv_repo.save_rows(csv_rows)

        # 9. Update upload status with final counts
        self._csv_repo.update_upload_status(upload_id, status, total_rows, error_rows)

        # 10. Log audit events
        self._log_event(
            event_type=EventType.CSV_UPLOAD,
            description=f"CSV file '{filename}' uploaded successfully: {total_rows} rows",
            metadata={
                "upload_id": str(upload_id),
                "filename": filename,
                "total_rows": total_rows,
                "s3_key": s3_key,
                "s3_bucket": bucket,
                "storage_provider": selected_provider,
            },
            user_id=user_id,
        )
        self._log_event(
            event_type=EventType.CSV_VALIDATION,
            description=(
                f"CSV validation completed for '{filename}': "
                f"{valid_rows} valid, {error_rows} errors (mode={validation_mode})"
            ),
            metadata={
                "upload_id": str(upload_id),
                "valid_rows": valid_rows,
                "error_rows": error_rows,
                "mode": validation_mode,
                "allow_duplicates": allow_duplicates,
            },
            user_id=user_id,
        )

        # 11. Return result
        return UploadResult(
            upload_id=upload_id,
            filename=filename,
            s3_key=s3_key,
            storage_provider=selected_provider,
            storage_bucket=bucket,
            total_rows=total_rows,
            valid_rows=valid_rows,
            error_rows=error_rows,
            validations=all_validation_errors,
            status=status,
        )

    def _resolve_storage_for_csv(
        self,
        storage_provider: str | None,
    ) -> tuple[str, IFileStoragePort, str]:
        provider = (storage_provider or self._settings.STORAGE_DEFAULT_PROVIDER or "minio").strip().lower()
        selected_storage = self._storage_by_provider.get(provider)
        if selected_storage is None:
            raise ValidationError(
                f"Unsupported storage provider '{provider}'. Allowed providers: minio, localstack"
            )

        if provider == "localstack":
            bucket = self._settings.LOCALSTACK_BUCKET_CSV
        else:
            bucket = self._settings.MINIO_BUCKET_CSV or self._settings.S3_BUCKET_CSV

        return provider, selected_storage, bucket

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _log_event(
        self,
        event_type: EventType,
        description: str,
        metadata: dict,
        user_id: UUID,
    ) -> None:
        """Create and persist a single audit-log event.

        Args:
            event_type: Category of the event.
            description: Human-readable summary.
            metadata: Structured key-value payload.
            user_id: UUID of the acting user.
        """
        event = Event(
            id=uuid4(),
            event_type=event_type,
            description=description,
            metadata=metadata,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )
        self._event_repo.log_event(event)

    def _validate_row(
        self,
        row_number: int,
        row_dict: dict,
        upload_id: UUID,
        allow_duplicates: bool,
        seen_hashes: set[str],
    ) -> CSVRow:
        """Validate a single CSV row and return a populated CSVRow entity.

        Checks for empty column values and, when ``allow_duplicates`` is ``False``,
        detects rows whose column values exactly match a previously seen row.

        Args:
            row_number: 1-indexed position of this row in the source file.
            row_dict: Raw column-name → value mapping from :class:`csv.DictReader`.
            upload_id: UUID of the parent upload (set on each CSVRow).
            allow_duplicates: When ``False``, duplicate rows produce an error entry.
            seen_hashes: Mutable set of MD5 hashes accumulated across all prior rows;
                updated in-place when this row is not a duplicate.

        Returns:
            A :class:`CSVRow` instance with any detected errors in ``validation_errors``.
        """
        row_errors: list[CSVValidationError] = []

        for col, val in row_dict.items():
            if val is None or str(val).strip() == "":
                row_errors.append(
                    CSVValidationError(
                        row_number=row_number,
                        column=str(col),
                        error_type="empty",
                        message=f"Column '{col}' is empty in row {row_number}",
                    )
                )
                continue

            type_error = self._validate_field_type(
                column=str(col),
                value=str(val).strip(),
                row_number=row_number,
            )
            if type_error is not None:
                row_errors.append(type_error)

        if not allow_duplicates:
            row_hash = hashlib.md5(
                "|".join(str(v) for v in row_dict.values()).encode("utf-8")
            ).hexdigest()
            if row_hash in seen_hashes:
                row_errors.append(
                    CSVValidationError(
                        row_number=row_number,
                        column="",
                        error_type="duplicate",
                        message=f"Row {row_number} is a duplicate of a previous row",
                    )
                )
            else:
                seen_hashes.add(row_hash)

        return CSVRow(
            id=None,
            upload_id=upload_id,
            row_number=row_number,
            row_data=row_dict,
            validation_errors=row_errors,
        )

    def _validate_field_type(
        self,
        column: str,
        value: str,
        row_number: int,
    ) -> CSVValidationError | None:
        """Validate type consistency based on column name conventions.

        The upload format is intentionally flexible (no fixed schema), so type
        checks are inferred from common naming patterns in column headers.
        """
        expected_type = self._expected_type_for_column(column)
        if expected_type is None:
            return None

        validators = {
            "int": self._is_int,
            "float": self._is_float,
            "date": self._is_date,
            "bool": self._is_bool,
            "email": self._is_email,
        }

        validator = validators.get(expected_type)
        if validator and validator(value):
            return None

        return CSVValidationError(
            row_number=row_number,
            column=column,
            error_type="type_mismatch",
            message=(
                f"Column '{column}' expects a value of type '{expected_type}' "
                f"in row {row_number}"
            ),
        )

    def _is_int(self, value: str) -> bool:
        try:
            int(value)
            return True
        except ValueError:
            return False

    def _is_float(self, value: str) -> bool:
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _is_date(self, value: str) -> bool:
        normalized = value.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(normalized)
            return True
        except ValueError:
            return False

    def _is_bool(self, value: str) -> bool:
        return value.lower() in {"true", "false", "1", "0", "yes", "no"}

    def _is_email(self, value: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))

    def _expected_type_for_column(self, column: str) -> str | None:
        """Infer expected type from common column-name patterns."""
        col = column.strip().lower()
        tokens = [t for t in re.split(r"[^a-z0-9]+", col) if t]

        int_tokens = {"id", "cantidad", "quantity", "count", "page", "size"}
        float_tokens = {
            "monto",
            "amount",
            "total",
            "subtotal",
            "precio",
            "price",
            "cost",
            "rate",
            "importe",
        }
        date_tokens = {"fecha", "date", "timestamp", "created", "updated"}
        bool_tokens = {"activo", "active", "enabled", "flag", "allow", "is", "has"}
        email_tokens = {"email", "correo", "mail"}

        if col.endswith("_id") or any(t in int_tokens for t in tokens):
            return "int"
        if any(t in float_tokens for t in tokens):
            return "float"
        if any(t in date_tokens for t in tokens):
            return "date"
        if col.startswith("is_") or col.startswith("has_") or any(t in bool_tokens for t in tokens):
            return "bool"
        if any(t in email_tokens for t in tokens):
            return "email"

        return None
