# Arquitectura del Proyecto

## Resumen

PruebaTecnica implementa una arquitectura hexagonal (ports and adapters) con FastAPI en backend y Angular en frontend. El dominio no depende de frameworks ni SDKs externos.

## Capas Backend

- Domain:
  - Modelos de negocio en src/domain/models
  - Puertos (interfaces) en src/domain/ports
  - Servicios de dominio en src/domain/services
  - Excepciones de negocio en src/domain/exceptions.py
- Application:
  - Rutas REST en src/application/api/v1
  - DTOs de request/response en src/application/schemas
  - Dependencias de auth/roles en src/application/dependencies.py
  - Mapeo de excepciones a contrato HTTP en src/application/exception_handlers.py
- Infrastructure:
  - Implementaciones concretas de puertos
  - SQL Server + SQLAlchemy en src/infrastructure/db y src/infrastructure/repositories
  - Storage S3/MinIO en src/infrastructure/storage/s3_adapter.py
  - Adaptadores IA (OpenAI, Gemini, Ollama) en src/infrastructure/ai
  - Composición de servicios por DI en src/infrastructure/di.py

## Flujo de Dependencias

- Domain define contratos.
- Infrastructure implementa contratos.
- Application orquesta casos y expone API.
- FastAPI monta middleware, handlers y routers desde src/main.py.

Regla principal: dependencias hacia adentro.

## Seleccion de Proveedor IA

La seleccion de proveedor es por variable AI_PROVIDER y se resuelve en src/infrastructure/di.py.

Opciones soportadas:

- openai
- gemini
- ollama

## Contrato API

Todos los endpoints JSON usan envoltura uniforme:

- success
- data
- error

Implementado en src/application/schemas/result.py.

## Frontend

Frontend SPA en Angular 21 + PrimeNG 21.

- Rutas protegidas por authGuard
- Redirecciones para invitados por guestGuard
- Interceptor de auth para Bearer token
- Interceptor de loading global
- Interceptor de contrato Result para validar payloads

Archivos clave:

- frontend/src/app/app.routes.ts
- frontend/src/app/core/auth.guard.ts
- frontend/src/app/core/auth.interceptor.ts
- frontend/src/app/core/loading.interceptor.ts
- frontend/src/app/core/result.interceptor.ts

## Persistencia

- DB: SQL Server via pyodbc
- ORM: SQLAlchemy 2
- Migraciones: Alembic
- Sesion DB: src/infrastructure/db/session.py

## Observabilidad Basica

- Request ID middleware
- Access logging middleware
- Endpoint de health infra: /api/v1/system/health

## Riesgos Operativos Relevantes

- Variables de entorno en shell pueden pisar valores del .env.
- Tener varias instancias backend en puertos distintos puede desviar requests.
- Modelos IA deprecados o sin credito generan 401/404/429.
