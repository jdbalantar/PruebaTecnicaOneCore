import {
  HttpErrorResponse,
  HttpEvent,
  HttpInterceptorFn,
  HttpResponse,
} from '@angular/common/http';
import { catchError, map, throwError } from 'rxjs';
import { ApiResult } from './api.models';

function normalizeErrorPayload(error: HttpErrorResponse): ApiResult<never> {
  const rawPayload = error.error as {
    success?: boolean;
    error?: { code?: string; message?: string; details?: unknown };
    detail?: string;
  };

  const message =
    rawPayload?.error?.message ||
    rawPayload?.detail ||
    error.message ||
    'Request failed';

  const code = rawPayload?.error?.code || `http_${error.status || 0}`;
  const details = rawPayload?.error?.details;

  return {
    success: false,
    data: null,
    error: {
      code,
      message,
      details,
    },
  };
}

function isApiJsonRequest(url: string, responseType: string): boolean {
  return url.includes('/api/v1/') && responseType === 'json';
}

function isResultEnvelope(body: unknown): body is ApiResult<unknown> {
  if (!body || typeof body !== 'object') {
    return false;
  }

  const value = body as { success?: unknown; data?: unknown; error?: unknown };
  return (
    typeof value.success === 'boolean' &&
    Object.hasOwn(value, 'data') &&
    Object.hasOwn(value, 'error')
  );
}

function toMalformedResultError(reqUrl: string): HttpErrorResponse {
  return new HttpErrorResponse({
    status: 502,
    statusText: 'Bad API Contract',
    error: {
      success: false,
      data: null,
      error: {
        code: 'malformed_result_envelope',
        message: 'API response does not match Result envelope contract.',
        details: { url: reqUrl },
      },
    },
  });
}

export const resultInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(
    map((event: HttpEvent<unknown>) => {
      if (
        event instanceof HttpResponse &&
        isApiJsonRequest(req.url, req.responseType) &&
        !isResultEnvelope(event.body)
      ) {
        throw toMalformedResultError(req.url);
      }

      return event;
    }),
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse)) {
        return throwError(() => error);
      }

      const normalizedPayload = normalizeErrorPayload(error);
      return throwError(
        () =>
          new HttpErrorResponse({
            error: normalizedPayload,
            headers: error.headers,
            status: error.status,
            url: error.url ?? undefined,
          })
      );
    })
  );
