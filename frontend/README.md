# Frontend - PruebaTecnica

SPA en Angular para operar los modulos de la evaluacion tecnica.

## Stack

- Angular 21
- PrimeNG 21
- PrimeIcons
- RxJS

## Modulos Principales

- Login
- Dashboard/API Console
- Upload CSV
- Analisis de documentos IA
- Eventos (filtros y export)
- Refresh token

## Seguridad y Flujo HTTP

- authGuard para rutas autenticadas
- guestGuard para ruta login
- authInterceptor para inyectar Bearer token
- loadingInterceptor para overlay de carga global
- resultInterceptor para validar contrato JSON (success/data/error)

## Configuracion API

Base URL configurada en:

- src/environments/environment.ts

## Desarrollo Local

1. Instalar dependencias:

- npm install

2. Iniciar frontend:

- npm start

3. Abrir navegador en:

- http://localhost:4200

## Scripts

- npm start
- npm run build
- npm run test

## Nota Operativa

Si el frontend muestra errores de backend inesperados, revisar:

- apiBaseUrl en environment.ts
- puerto real donde esta corriendo uvicorn
- token valido en almacenamiento local
