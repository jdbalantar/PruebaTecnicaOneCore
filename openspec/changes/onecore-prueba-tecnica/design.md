# Design - onecore-prueba-tecnica

## Mapa de Capas

- src/domain
  - modelos
  - puertos
  - servicios
  - excepciones
- src/application
  - api/v1 routers
  - schemas
  - dependencies
  - exception handlers
- src/infrastructure
  - db/session/models
  - repositories
  - storage s3
  - ai adapters
  - di
- src/main.py
  - middleware
  - app factory
  - router registration

## Mapa Frontend

- frontend/src/app/app.routes.ts
  - login protegido por guestGuard
  - app/\* protegido por authGuard
- frontend/src/app/core
  - api.service
  - auth.service
  - interceptors (auth/loading/result)
- frontend/src/app/layout
  - topbar/sidebar/menu

## Flujo End-to-End (Documento)

1. Frontend envia archivo a /api/v1/documents/analyze.
2. Router valida content-type.
3. DocumentAnalysisService sube archivo a S3.
4. Adapter IA clasifica y extrae.
5. Se persiste Document.
6. Se registran eventos.
7. Respuesta vuelve en contrato Result.

## Decisiones Clave

- Contrato uniforme de respuestas JSON.
- Seleccion de proveedor IA por config.
- Frontend valida contrato en interceptor.
- Health endpoint infra para diagnostico runtime.

## Riesgos y Mitigaciones

- Riesgo: overrides de entorno en shell.
  - Mitigacion: documentar limpieza y prioridad .env.
- Riesgo: puertos backend inconsistentes.
  - Mitigacion: documentar apiBaseUrl y puerto activo.
- Riesgo: cuotas/modelos deprecados en IA.
  - Mitigacion: documentar troubleshooting y modelos vigentes.
