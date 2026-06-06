import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  AnalysisResultResponse,
  ApiResult,
  EventFilters,
  EventPageResponse,
  LoginRequest,
  SystemHealthResponse,
  TokenResponse,
  UploadResultResponse
} from './api.models';
import { SKIP_LOADING } from './loading.context';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private readonly http: HttpClient) {}

  login(payload: LoginRequest): Observable<ApiResult<TokenResponse>> {
    return this.http.post<ApiResult<TokenResponse>>(`${this.baseUrl}/auth/login`, payload);
  }

  refreshToken(token: string): Observable<ApiResult<TokenResponse>> {
    return this.http.post<ApiResult<TokenResponse>>(`${this.baseUrl}/auth/refresh`, { token });
  }

  uploadCsv(
    file: File,
    validationMode: string,
    allowDuplicates: boolean,
    storageProvider: string
  ): Observable<ApiResult<UploadResultResponse>> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('validation_mode', validationMode);
    formData.append('allow_duplicates', String(allowDuplicates));
    formData.append('storage_provider', storageProvider);

    return this.http.post<ApiResult<UploadResultResponse>>(`${this.baseUrl}/files/upload`, formData);
  }

  analyzeDocument(file: File, storageProvider: string): Observable<ApiResult<AnalysisResultResponse>> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('storage_provider', storageProvider);

    return this.http.post<ApiResult<AnalysisResultResponse>>(`${this.baseUrl}/documents/analyze`, formData);
  }

  listEvents(filters: EventFilters): Observable<ApiResult<EventPageResponse>> {
    let params = new HttpParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    });

    return this.http.get<ApiResult<EventPageResponse>>(`${this.baseUrl}/events`, { params });
  }

  exportEvents(filters: EventFilters): Observable<Blob> {
    let params = new HttpParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    });

    return this.http.get(`${this.baseUrl}/events/export`, {
      params,
      responseType: 'blob'
    });
  }

  getSystemHealth(): Observable<ApiResult<SystemHealthResponse>> {
    return this.http.get<ApiResult<SystemHealthResponse>>(`${this.baseUrl}/system/health`, {
      context: new HttpContext().set(SKIP_LOADING, true)
    });
  }
}
