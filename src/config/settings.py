"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the PruebaTecnica application.

    All values can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --------------- App ---------------
    APP_NAME: str = "PruebaTecnica"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str

    # --------------- JWT RS256 ---------------
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY: str  # PEM-encoded RSA private key
    JWT_PUBLIC_KEY: str  # PEM-encoded RSA public key
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # --------------- SQL Server ---------------
    DB_HOST: str = "localhost"
    DB_PORT: int = 1433
    DB_NAME: str = "prueba_tecnica"
    DB_USER: str
    DB_PASSWORD: str
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"

    # --------------- AWS S3 ---------------
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET_CSV: str = "onecore-uploads"
    S3_BUCKET_DOCS: str = "onecore-documents"

    # --------------- AI Provider ---------------
    AI_PROVIDER: str = "gemini"

    # --------------- Gemini ---------------
    GEMINI_API_KEY: str = ""
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_MODEL_CLASSIFY: str = "gemini-2.5-flash-lite"
    GEMINI_MODEL_EXTRACT: str = "gemini-2.5-flash-lite"

    # --------------- CSV Validation ---------------
    CSV_MAX_FILE_SIZE_MB: int = 10
    CSV_MAX_ROWS: int = 50000


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings.

    Uses lru_cache so the .env file is only read once per process lifetime.
    """
    return Settings()
