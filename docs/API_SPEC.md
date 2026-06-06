# Especificacion API (Estado Actual)

## Base URL

- Backend local: http://127.0.0.1:8000 o puerto configurado en uvicorn
- Prefijo API: /api/v1

## Contrato de Respuesta JSON

Formato uniforme para endpoints JSON:

- success: boolean
- data: objeto o null
- error: { code, message, details } o null

Nota:

- El endpoint de exportacion de eventos devuelve Blob (xlsx), no usa envoltura JSON.

## Autenticacion

- Esquema: Bearer JWT
- Login y refresh no requieren token previo de Authorization.

## Endpoints

### Auth

- POST /api/v1/auth/login
  - body: { username, password }
  - response data: { access_token, token_type, expires_in }

- POST /api/v1/auth/refresh
  - body: { token }
  - response data: { access_token, token_type, expires_in }

### Files

- POST /api/v1/files/upload
  - auth: requerido
  - roles: admin o uploader
  - multipart:
    - file (csv)
    - validation_mode (strict|lenient)
    - allow_duplicates (boolean)
  - response data:
    - upload_id
    - filename
    - s3_key
    - total_rows
    - valid_rows
    - error_rows
    - status
    - validations[]

### Documents

- POST /api/v1/documents/analyze
  - auth: requerido
  - content types soportados:
    - image/jpeg
    - image/png
    - application/pdf
  - response data:
    - document_id
    - doc_type (invoice|information|unknown)
    - confidence
    - extracted_data
    - ai_model
    - fallback_used
    - fallback_reason

### Events

- GET /api/v1/events
  - auth: requerido
  - filtros:
    - event_type
    - description
    - date_from
    - date_to
    - page
    - page_size
  - response data:
    - items[]
    - total
    - page
    - page_size

- GET /api/v1/events/export
  - auth: requerido
  - filtros iguales a list
  - respuesta: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

### System

- GET /api/v1/system/health
  - auth: no requerido
  - response data:
    - status
    - timestamp
    - services.api
    - services.database
    - services.storage

## Codigos de Error de Dominio Frecuentes

- auth_error
- invalid_token
- not_found
- permission_denied
- validation_error
- request_validation_error
- storage_unavailable
- ai_unavailable
- internal_server_error

## Eventos de Auditoria (EventType)

- user_login
- token_renewal
- csv_upload
- csv_validation
- doc_upload
- ai_classification
- ai_extraction
- event_export
- error
