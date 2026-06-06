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

    # --------------- OpenAI ---------------
    AI_PROVIDER: str = "ollama"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_CLASSIFY: str = "gpt-4o-mini"
    OPENAI_MODEL_EXTRACT: str = "gpt-4o"

    # --------------- Gemini ---------------
    GEMINI_API_KEY: str = ""
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_MODEL_CLASSIFY: str = "gemini-2.5-flash-lite"
    GEMINI_MODEL_EXTRACT: str = "gemini-2.5-flash-lite"

    # --------------- Ollama (Local) ---------------
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL_CLASSIFY: str = "llava:7b"
    OLLAMA_MODEL_EXTRACT: str = "llava:7b"
    OLLAMA_REQUEST_TIMEOUT_SECONDS: int = 180
    OLLAMA_OCR_TEXT_MAX_CHARS: int = 12000

    # --------------- OCR (Preprocessing) ---------------
    OCR_ENABLED: bool = True
    OCR_LANG: str = "eng"
    OCR_TESSERACT_CMD: str | None = None
    OCR_PDF_MAX_PAGES: int = 5
    OCR_MIN_TEXT_CHARS: int = 40

    # --------------- CSV Validation ---------------
    CSV_MAX_FILE_SIZE_MB: int = 10
    CSV_MAX_ROWS: int = 50000


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings.

    Uses lru_cache so the .env file is only read once per process lifetime.
    """
    return Settings()
