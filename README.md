# PruebaTecnica - OneCore

Sistema full-stack para evaluacion tecnica con:

- Autenticacion JWT (RS256)
- Carga y validacion de CSV
- Analisis de documentos con IA (Gemini)
- Historial de eventos con filtros y exportacion a Excel
- API REST en FastAPI + frontend SPA en Angular

## Tabla de Contenido

- Vision del proyecto
- Tecnologias y frameworks
- Arquitectura
- Estructura del repositorio
- Configuracion de entorno
- Levantar proyecto en desarrollo
- Endpoints principales
- Testing, calidad y CI
- Docker
- Troubleshooting
- Documentacion adicional

## Vision del Proyecto

Este repositorio implementa la solucion de la prueba tecnica de OneCore y evoluciono hacia una arquitectura modular, con separacion clara entre dominio de negocio, API y adapters de infraestructura.

El foco funcional actual incluye:

- Login y refresh token con JWT firmado
- Subida de CSV con validaciones por fila
- Subida de PDF/JPG/PNG para clasificacion y extraccion de datos
- Registro de eventos de auditoria
- Consulta y exportacion de eventos

## Tecnologias y Frameworks

Backend:

- Python 3.11+
- FastAPI
- SQLAlchemy 2
- Alembic
- PyODBC (SQL Server)
- Pydantic Settings
- python-jose + passlib/bcrypt
- boto3 (S3/MinIO)
- openpyxl (export xlsx)
- httpx

Frontend:

- Angular 21
- PrimeNG 21
- PrimeIcons
- RxJS

DevOps/Calidad:

- Pytest + pytest-cov
- Ruff
- GitHub Actions
- Docker Compose

## Arquitectura

### Backend (Hexagonal)

- Domain:
  - Entidades, enums y reglas de negocio
  - Puertos (interfaces)
  - Servicios de dominio
- Application:
  - Routers API v1
  - Schemas de request/response
  - Dependencias de auth/roles
  - Exception handlers con contrato uniforme
- Infrastructure:
  - Repositorios SQL Server
  - Adapter S3/MinIO
  - Adapter IA (Gemini)
  - DI container

Punto de entrada:

- src/main.py

### Frontend (SPA)

- Ruteo protegido por guards
- Interceptores para:
  - Authorization Bearer
  - Loading overlay global
  - Validacion del contrato Result
- Layout con topbar, sidebar y dashboard operativo

## Estructura del Repositorio

- src/: backend
- frontend/: SPA Angular
- tests/: unit e integration tests
- alembic/: migraciones
- openspec/: artefactos de especificacion
- docs/: documentacion tecnica actualizada

## Configuracion de Entorno

1. Copiar .env.example a .env.
2. Completar credenciales y llaves.
3. Configurar proveedor IA con AI_PROVIDER=gemini.

Variables relevantes:

- JWT: JWT_PRIVATE_KEY, JWT_PUBLIC_KEY
- DB: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_DRIVER
- S3: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_ENDPOINT_URL
- IA: AI_PROVIDER, GEMINI_API_KEY, GEMINI_API_BASE, GEMINI_MODEL_CLASSIFY, GEMINI_MODEL_EXTRACT

## Levantar Proyecto en Desarrollo

### 1) Backend

Desde raiz del repo:

- pip install -e .[test]
- alembic upgrade head
- python -m uvicorn src.main:app --host 127.0.0.1 --port 8010 --reload

Nota:

- Si tenes variables de entorno previas en la shell, pueden pisar .env.

### 2) Frontend

Desde frontend:

- npm install
- npm start

Verificar API base en:

- frontend/src/environments/environment.ts

## Endpoints Principales

Prefijo:

- /api/v1

Auth:

- POST /auth/login
- POST /auth/refresh

Files:

- POST /files/upload (admin/uploader)

Documents:

- POST /documents/analyze (jwt requerido)

Events:

- GET /events
- GET /events/export (xlsx)

System:

- GET /system/health

Contrato JSON:

- success
- data
- error

## Testing, Calidad y CI

Backend:

- pytest --cov=src --cov-report=term-missing
- pytest tests/unit --no-cov -q
- pytest tests/integration --no-cov -q
- ruff check src tests
- ruff format --check src tests

Frontend:

- npm run test
- npm run build

CI:

- .github/workflows/ci.yml
- Lint y tests con umbral de cobertura 80%

## Docker

Stack local con app + SQL Server + MinIO:

- docker-compose up --build

Migraciones dentro de contenedor app:

- docker-compose exec app alembic upgrade head

## Troubleshooting

1. ai_unavailable con 429 en Gemini:

- revisar creditos y billing del proyecto en AI Studio

2. 401 con Gemini:

- revisar GEMINI_API_KEY, proyecto asociado y modelo configurado

3. requests pegando al backend equivocado:

- revisar frontend/src/environments/environment.ts
- evitar multiples instancias uvicorn en puertos distintos

4. errores SQL Server/ODBC:

- validar DB_DRIVER y conectividad DB

## Documentacion Adicional

- docs/ARCHITECTURE.md
- docs/API_SPEC.md
- docs/DEVELOPMENT.md
- Documentacion.txt

## Estado Actual de IA

El backend usa Gemini como proveedor IA soportado y activo. En escenario de cuotas, pueden ocurrir degradaciones por disponibilidad del proveedor.
