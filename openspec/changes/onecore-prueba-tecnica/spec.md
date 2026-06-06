# Spec - onecore-prueba-tecnica

## 1. Arquitectura Objetivo

El sistema debe reflejar arquitectura hexagonal con:

- dominio desacoplado de framework
- puertos en dominio
- adapters en infraestructura
- routers y schemas en capa application

## 2. Contrato API

Los endpoints JSON deben usar envoltura uniforme:

- success: boolean
- data: payload o null
- error: { code, message, details } o null

Excepcion:

- /api/v1/events/export devuelve stream Blob xlsx.

## 3. Endpoints Requeridos

- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/files/upload
- POST /api/v1/documents/analyze
- GET /api/v1/events
- GET /api/v1/events/export
- GET /api/v1/system/health

## 4. Seguridad

- JWT Bearer para rutas protegidas
- Guard de roles en upload CSV: admin o uploader

## 5. IA

Proveedor soportado por AI_PROVIDER:

- gemini

Debe existir documentacion de variables Gemini y troubleshooting de errores 401/404/429.

## 6. Operacion Local

Debe incluirse guia de:

- instalacion backend
- migraciones alembic
- arranque uvicorn
- instalacion y arranque frontend
- alineacion de apiBaseUrl

## 7. Calidad

Debe documentarse:

- comandos de tests
- lint/formato
- CI y coverage objetivo
