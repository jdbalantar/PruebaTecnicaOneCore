"""System router — infrastructure health endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import get_settings
from src.infrastructure.db.session import get_db
from src.infrastructure.storage.s3_adapter import S3FileStorageAdapter
from src.application.schemas.result import Result, ok
from src.application.schemas.system import ServiceHealthResponse, SystemHealthResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def system_health(
    db: Annotated[Session, Depends(get_db)],
) -> Result[SystemHealthResponse]:
    """Return infrastructure health summary (API, DB, and storage)."""
    db_status = "up"
    db_detail = "query ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive runtime check
        db_status = "down"
        db_detail = str(exc)

    settings = get_settings()

    minio = S3FileStorageAdapter(
        settings,
        endpoint_url=settings.MINIO_ENDPOINT_URL or settings.S3_ENDPOINT_URL,
        access_key_id=settings.MINIO_ACCESS_KEY_ID or settings.AWS_ACCESS_KEY_ID,
        secret_access_key=settings.MINIO_SECRET_ACCESS_KEY or settings.AWS_SECRET_ACCESS_KEY,
    )
    minio_bucket = settings.MINIO_BUCKET_CSV or settings.S3_BUCKET_CSV
    minio_ok, minio_detail = minio.health_check(minio_bucket)
    minio_status = "up" if minio_ok else "down"

    s3 = S3FileStorageAdapter(
        settings,
        endpoint_url=settings.LOCALSTACK_ENDPOINT_URL,
        access_key_id=settings.LOCALSTACK_ACCESS_KEY_ID,
        secret_access_key=settings.LOCALSTACK_SECRET_ACCESS_KEY,
    )
    s3_ok, s3_detail = s3.health_check(settings.LOCALSTACK_BUCKET_CSV)
    s3_status = "up" if s3_ok else "down"

    overall = (
        "ok"
        if db_status == "up" and minio_status == "up" and s3_status == "up"
        else "degraded"
    )

    return ok(
        SystemHealthResponse(
            status=overall,
            timestamp=datetime.now(timezone.utc).isoformat(),
            services={
                "api": ServiceHealthResponse(status="up", detail="running"),
                "database": ServiceHealthResponse(status=db_status, detail=db_detail),
                "minio": ServiceHealthResponse(status=minio_status, detail=minio_detail),
                "s3": ServiceHealthResponse(status=s3_status, detail=s3_detail),
                # Backward compatibility: keep existing key used by the frontend.
                "storage": ServiceHealthResponse(status=minio_status, detail=minio_detail),
            },
        )
    )
