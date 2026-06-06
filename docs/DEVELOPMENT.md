# Guia de Desarrollo

## Requisitos

Backend:

- Python 3.11+
- ODBC Driver 17 for SQL Server
- SQL Server accesible
- Credenciales AWS/MinIO para S3

Frontend:

- Node.js 20+
- npm 10+

Opcional:

- Docker + Docker Compose
- Ollama (si AI_PROVIDER=ollama)
- Tesseract OCR (si usas OCR con Ollama)

## Setup Backend

1. Instalar dependencias:

- pip install -e .[test]

2. Configurar variables:

- copiar .env.example a .env
- completar credenciales y llaves JWT

3. Ejecutar migraciones:

- alembic upgrade head

4. Levantar API (ejemplo):

- python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload

## Setup Frontend

1. Entrar a carpeta frontend.
2. Instalar dependencias:

- npm install

3. Verificar apiBaseUrl en frontend/src/environments/environment.ts.
4. Levantar frontend:

- npm start

## Variables IA Clave

- AI_PROVIDER: openai | gemini | ollama

OpenAI:

- OPENAI_API_KEY
- OPENAI_MODEL_CLASSIFY
- OPENAI_MODEL_EXTRACT

Gemini:

- GEMINI_API_KEY
- GEMINI_API_BASE
- GEMINI_MODEL_CLASSIFY
- GEMINI_MODEL_EXTRACT

Ollama:

- OLLAMA_BASE_URL
- OLLAMA_MODEL_CLASSIFY
- OLLAMA_MODEL_EXTRACT
- OLLAMA_REQUEST_TIMEOUT_SECONDS
- OLLAMA_OCR_TEXT_MAX_CHARS

OCR:

- OCR_ENABLED
- OCR_LANG
- OCR_TESSERACT_CMD
- OCR_PDF_MAX_PAGES
- OCR_MIN_TEXT_CHARS

## Comandos de Calidad y Tests

Backend:

- pytest --cov=src --cov-report=term-missing
- pytest tests/unit --no-cov -q
- pytest tests/integration --no-cov -q
- ruff check src tests
- ruff format --check src tests

Frontend:

- npm run test
- npm run build

## CI

GitHub Actions en .github/workflows/ci.yml:

- Lint con Ruff
- Tests con coverage >= 80%

## Troubleshooting

1. Error ai_unavailable con 429:

- revisar credito/cuota del proveedor IA

2. Error 401 en Gemini:

- validar GEMINI_API_KEY, proyecto y billing
- validar modelo activo y no deprecado

3. Error de conexion a Ollama:

- verificar servicio en OLLAMA_BASE_URL
- verificar modelo descargado

4. Requests yendo al backend equivocado:

- revisar frontend/src/environments/environment.ts
- evitar multiples uvicorn activos en puertos distintos

5. DB connection issues:

- revisar DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_DRIVER
