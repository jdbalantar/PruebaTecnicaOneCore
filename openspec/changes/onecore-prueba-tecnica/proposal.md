# Proposal - onecore-prueba-tecnica

## Resumen Ejecutivo

Actualizar y alinear toda la documentacion del proyecto al estado real del codigo implementado, incluyendo backend, frontend y operacion local.

## Motivacion

Los artefactos previos de especificacion y documentacion describian estructura y contratos que no coinciden completamente con el repositorio actual. Esto afecta onboarding, mantenimiento y soporte.

## Objetivos

- Documentar stack real y arquitectura vigente.
- Documentar setup de desarrollo backend/frontend.
- Documentar contrato API real (Result envelope).
- Documentar integraciones (SQL Server, S3/MinIO, proveedores IA).
- Corregir artefactos openspec para reflejar implementacion actual.

## Alcance

Incluye:

- README.md
- Documentacion.txt
- frontend/README.md
- docs/ARCHITECTURE.md
- docs/API_SPEC.md
- docs/DEVELOPMENT.md
- openspec/changes/onecore-prueba-tecnica/\*

No incluye:

- cambios funcionales en logica de negocio
- modificaciones de contratos HTTP en runtime

## Criterios de Exito

- Documentacion consistente con el codigo actual.
- Instrucciones de levantamiento local reproducibles.
- Descripcion clara de dependencias, arquitectura y troubleshooting.
