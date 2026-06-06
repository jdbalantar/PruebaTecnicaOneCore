"""Unit tests for FileUploadService — CSV validation, S3 storage, and persistence."""

import csv
import io
import pytest
from unittest.mock import call
from uuid import uuid4

from src.domain.exceptions import ValidationError
from src.domain.services.file_upload_service import FileUploadService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid4()


def _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings) -> FileUploadService:
    """Instantiate FileUploadService with injected mocks."""
    return FileUploadService(
        csv_repo=mock_csv_repo,
        storage=mock_storage,
        event_repo=mock_event_repo,
        settings=mock_settings,
    )


def _csv_bytes(rows: list[dict], headers: list[str] | None = None) -> bytes:
    """Encode a list of dicts as UTF-8 CSV bytes."""
    buf = io.StringIO()
    if not headers and rows:
        headers = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=headers or [])
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


_VALID_ROWS = [
    {"name": "Alice", "age": "30", "city": "BA"},
    {"name": "Bob", "age": "25", "city": "Córdoba"},
    {"name": "Carlos", "age": "40", "city": "Rosario"},
]

_VALID_CSV = _csv_bytes(_VALID_ROWS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFileUploadValidation:
    """Tests for FileUploadService.upload_and_validate."""

    def test_valid_csv_is_accepted(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """A well-formed CSV with no errors must return a completed UploadResult."""
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        result = service.upload_and_validate(
            _VALID_CSV, "data.csv", "lenient", False, _USER_ID
        )

        assert result.total_rows == 3
        assert result.error_rows == 0
        assert result.status == "completed"

    def test_file_exceeds_size_limit_raises_validation_error(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """A file larger than CSV_MAX_FILE_SIZE_MB must raise ValidationError."""
        oversized = b"x" * (mock_settings.CSV_MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        with pytest.raises(ValidationError, match="size"):
            service.upload_and_validate(oversized, "huge.csv", "lenient", False, _USER_ID)

    def test_non_utf8_file_raises_validation_error(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """Binary content that is not valid UTF-8 must raise ValidationError."""
        bad_bytes = b"\xff\xfe\x00\x01\xde\xad\xbe\xef"
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        with pytest.raises(ValidationError, match="UTF-8"):
            service.upload_and_validate(bad_bytes, "bad.csv", "lenient", False, _USER_ID)

    def test_row_count_exceeds_limit_raises_validation_error(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """A CSV with more rows than CSV_MAX_ROWS must raise ValidationError."""
        mock_settings.CSV_MAX_ROWS = 2  # override limit for this test
        too_many_rows = [{"col": f"v{i}"} for i in range(3)]
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        with pytest.raises(ValidationError, match="rows"):
            service.upload_and_validate(
                _csv_bytes(too_many_rows), "big.csv", "lenient", False, _USER_ID
            )

    def test_empty_value_detected_in_strict_mode(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """A row with an empty column value in strict mode must raise ValidationError."""
        rows = [{"col1": "", "col2": "value"}]
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        with pytest.raises(ValidationError):
            service.upload_and_validate(_csv_bytes(rows), "f.csv", "strict", False, _USER_ID)

    def test_empty_value_collected_in_lenient_mode(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """A row with an empty column value in lenient mode must be collected as an error."""
        rows = [{"col1": "", "col2": "value"}]
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        result = service.upload_and_validate(_csv_bytes(rows), "f.csv", "lenient", False, _USER_ID)

        assert result.error_rows == 1
        assert len(result.validations) >= 1
        assert result.validations[0].error_type == "empty"
        assert result.validations[0].column == "col1"

    def test_duplicate_rows_detected_when_not_allowed(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """Two identical rows with allow_duplicates=False must produce a duplicate error."""
        rows = [{"col1": "dup", "col2": "dup"}, {"col1": "dup", "col2": "dup"}]
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        result = service.upload_and_validate(
            _csv_bytes(rows), "f.csv", "lenient", False, _USER_ID
        )

        dup_errors = [e for e in result.validations if e.error_type == "duplicate"]
        assert len(dup_errors) >= 1

    def test_duplicate_rows_allowed_when_flag_set(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """Two identical rows with allow_duplicates=True must produce no duplicate errors."""
        rows = [{"col1": "dup", "col2": "dup"}, {"col1": "dup", "col2": "dup"}]
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        result = service.upload_and_validate(
            _csv_bytes(rows), "f.csv", "lenient", True, _USER_ID
        )

        dup_errors = [e for e in result.validations if e.error_type == "duplicate"]
        assert len(dup_errors) == 0

    def test_upload_saved_to_s3(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """S3 upload must be called exactly once with the file bytes and CSV content-type."""
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        service.upload_and_validate(_VALID_CSV, "data.csv", "lenient", False, _USER_ID)

        mock_storage.upload_file.assert_called_once()
        call_kwargs = mock_storage.upload_file.call_args.kwargs
        assert call_kwargs["file_bytes"] == _VALID_CSV
        assert call_kwargs["content_type"] == "text/csv"
        assert call_kwargs["bucket"] == mock_settings.S3_BUCKET_CSV

    def test_rows_saved_to_db(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """The CSV repository's save_rows must be called with all parsed rows."""
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        service.upload_and_validate(_VALID_CSV, "data.csv", "lenient", False, _USER_ID)

        mock_csv_repo.save_rows.assert_called_once()
        saved_rows = mock_csv_repo.save_rows.call_args.args[0]
        assert len(saved_rows) == 3

    def test_event_logged_after_upload(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """Two audit events (CSV_UPLOAD and CSV_VALIDATION) must be logged."""
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        service.upload_and_validate(_VALID_CSV, "data.csv", "lenient", False, _USER_ID)

        assert mock_event_repo.log_event.call_count == 2
        logged_types = {c.args[0].event_type for c in mock_event_repo.log_event.call_args_list}
        from src.domain.models.event import EventType
        assert EventType.CSV_UPLOAD in logged_types
        assert EventType.CSV_VALIDATION in logged_types

    def test_upload_result_contains_correct_counts(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """UploadResult must reflect the exact count of total, valid, and error rows."""
        rows = [
            {"col1": "good", "col2": "value"},
            {"col1": "", "col2": "value"},   # empty → error
            {"col1": "also_good", "col2": "v"},
        ]
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        result = service.upload_and_validate(
            _csv_bytes(rows), "f.csv", "lenient", False, _USER_ID
        )

        assert result.total_rows == 3
        assert result.error_rows == 1
        assert result.valid_rows == 2

    @pytest.mark.parametrize(
        "validation_mode,has_errors,should_raise",
        [
            ("strict", True, True),    # strict + errors → raises ValidationError
            ("lenient", True, False),  # lenient + errors → completed
            ("strict", False, False),  # strict + no errors → completed
            ("lenient", False, False), # lenient + no errors → completed
        ],
    )
    def test_status_based_on_mode_and_errors(
        self,
        validation_mode,
        has_errors,
        should_raise,
        mock_csv_repo,
        mock_storage,
        mock_event_repo,
        mock_settings,
    ):
        """Strict mode with errors must raise; all other combinations must return 'completed'."""
        if has_errors:
            rows = [{"col1": "", "col2": "value"}]  # empty col → validation error
        else:
            rows = [{"col1": "ok", "col2": "value"}]

        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        if should_raise:
            with pytest.raises(ValidationError):
                service.upload_and_validate(
                    _csv_bytes(rows), "f.csv", validation_mode, False, _USER_ID
                )
        else:
            result = service.upload_and_validate(
                _csv_bytes(rows), "f.csv", validation_mode, False, _USER_ID
            )
            assert result.status == "completed"

    def test_s3_key_contains_user_id_and_filename(
        self, mock_csv_repo, mock_storage, mock_event_repo, mock_settings
    ):
        """The S3 key used for upload must embed the user UUID and original filename."""
        service = _make_service(mock_csv_repo, mock_storage, mock_event_repo, mock_settings)

        service.upload_and_validate(_VALID_CSV, "report.csv", "lenient", False, _USER_ID)

        call_kwargs = mock_storage.upload_file.call_args.kwargs
        assert str(_USER_ID) in call_kwargs["key"]
        assert "report.csv" in call_kwargs["key"]
