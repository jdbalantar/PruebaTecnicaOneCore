import { HttpErrorResponse } from '@angular/common/http';

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiResult<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface ValidationErrorItem {
  row_number: number;
  column: string;
  error_type: string;
  message: string;
}

export interface UploadResultResponse {
  upload_id: string;
  filename: string;
  s3_key: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  status: string;
  validations: ValidationErrorItem[];
}

export interface AnalysisResultResponse {
  document_id: string;
  doc_type: string;
  confidence: number;
  extracted_data: Record<string, unknown> | null;
  ai_model: string;
  fallback_used?: boolean;
  fallback_reason?: string | null;
}

export interface EventResponse {
  id: string;
  event_type: string;
  description: string;
  metadata: Record<string, unknown>;
  user_id: string | null;
  created_at: string;
}

export interface EventPageResponse {
  items: EventResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface EventFilters {
  event_type?: string;
  description?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface ServiceHealth {
  status: 'up' | 'down';
  detail: string;
}

export interface SystemHealthResponse {
  status: 'ok' | 'degraded';
  timestamp: string;
  services: {
    api: ServiceHealth;
    database: ServiceHealth;
    storage: ServiceHealth;
  };
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const payload = error.error as {
      error?: { message?: string };
      detail?: string;
    };
    return payload?.error?.message || payload?.detail || error.message || fallback;
  }

  if (typeof error === 'object' && error !== null) {
    const maybeError = error as { message?: string };
    if (typeof maybeError.message === 'string' && maybeError.message.trim()) {
      return maybeError.message;
    }
  }

  return fallback;
}
