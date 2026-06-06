"""SQLAlchemy ORM models for the PruebaTecnica application.

All models map to SQL Server tables and follow the schema defined in the
technical specification (spec.md §2).  JSON columns use NVARCHAR(MAX)
via sqlalchemy.types.JSON, which serialises to/from Python dicts.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.infrastructure.db.base import Base


class UserModel(Base):
    """ORM model for the ``users`` table.

    Stores user accounts with role-based access control.  ``password_hash``
    is nullable to support anonymous users created on first login.
    """

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint("rol IN ('admin', 'uploader', 'viewer')", name="ck_users_rol"),
        Index("idx_users_username", "username"),
        Index("idx_users_rol", "rol"),
        Index("idx_users_active", "is_active"),
    )

    id_usuario: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER,
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rol: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    csv_uploads: Mapped[list["CSVUploadModel"]] = relationship(
        "CSVUploadModel", back_populates="user", lazy="noload"
    )
    documents: Mapped[list["DocumentModel"]] = relationship(
        "DocumentModel", back_populates="user", lazy="noload"
    )
    events: Mapped[list["EventModel"]] = relationship(
        "EventModel", back_populates="user", lazy="noload"
    )


class CSVUploadModel(Base):
    """ORM model for the ``csv_uploads`` table.

    Stores metadata for each CSV file upload, including S3 location,
    validation parameters, row counts, and processing status.
    """

    __tablename__ = "csv_uploads"

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'completed', 'failed')",
            name="ck_csv_uploads_status",
        ),
        Index("idx_csv_uploads_user_date", "user_id", "created_at"),
        Index("idx_csv_uploads_status", "status"),
        Index("idx_csv_uploads_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER,
        ForeignKey("users.id_usuario", ondelete="NO ACTION"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    params_json: Mapped[str] = mapped_column(String, nullable=False)  # JSON string
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="csv_uploads")
    rows: Mapped[list["CSVRowModel"]] = relationship(
        "CSVRowModel", back_populates="upload", lazy="noload"
    )


class CSVRowModel(Base):
    """ORM model for the ``csv_rows`` table.

    Stores individual parsed rows from a CSV upload, including the raw
    row data as JSON and any per-row validation errors.
    """

    __tablename__ = "csv_rows"

    __table_args__ = (
        Index("idx_csv_rows_upload", "upload_id"),
        Index("idx_csv_rows_upload_row", "upload_id", "row_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER,
        ForeignKey("csv_uploads.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    upload: Mapped["CSVUploadModel"] = relationship(
        "CSVUploadModel", back_populates="rows"
    )


class DocumentModel(Base):
    """ORM model for the ``documents`` table.

    Stores uploaded documents (PDF / image) alongside their AI classification
    results and extracted structured data.
    """

    __tablename__ = "documents"

    __table_args__ = (
        CheckConstraint(
            "file_type IN ('pdf', 'jpg', 'png')", name="ck_documents_file_type"
        ),
        CheckConstraint(
            "doc_type IN ('invoice', 'information') OR doc_type IS NULL",
            name="ck_documents_doc_type",
        ),
        Index("idx_documents_user_date", "user_id", "created_at"),
        Index("idx_documents_type", "doc_type"),
        Index("idx_documents_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER,
        ForeignKey("users.id_usuario", ondelete="NO ACTION"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="documents")


class EventModel(Base):
    """ORM model for the ``events`` table.

    Generic event log for all system activities.  ``user_id`` is nullable
    to accommodate system-generated events with no associated user.
    """

    __tablename__ = "events"

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'user_login', 'token_renewal', 'csv_upload', 'csv_validation',"
            "'doc_upload', 'ai_classification', 'ai_extraction', 'event_export', 'error'"
            ")",
            name="ck_events_event_type",
        ),
        Index("idx_events_type_date", "event_type", "timestamp"),
        Index("idx_events_user_date", "user_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER,
        ForeignKey("users.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped["UserModel | None"] = relationship(
        "UserModel", back_populates="events"
    )
