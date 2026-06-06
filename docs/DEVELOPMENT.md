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

- AI_PROVIDER: gemini

Gemini:

- GEMINI_API_KEY
- GEMINI_API_BASE
- GEMINI_MODEL_CLASSIFY
- GEMINI_MODEL_EXTRACT

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

3. Requests yendo al backend equivocado:

- revisar frontend/src/environments/environment.ts
- evitar multiples uvicorn activos en puertos distintos

4. DB connection issues:

- revisar DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_DRIVER
