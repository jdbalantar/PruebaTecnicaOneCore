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
    storage = S3FileStorageAdapter(settings)
    storage_ok, storage_detail = storage.health_check(settings.S3_BUCKET_CSV)
    storage_status = "up" if storage_ok else "down"

    overall = "ok" if db_status == "up" and storage_status == "up" else "degraded"

    return ok(
        SystemHealthResponse(
            status=overall,
            timestamp=datetime.now(timezone.utc).isoformat(),
            services={
                "api": ServiceHealthResponse(status="up", detail="running"),
                "database": ServiceHealthResponse(status=db_status, detail=db_detail),
                "storage": ServiceHealthResponse(status=storage_status, detail=storage_detail),
            },
        )
    )
