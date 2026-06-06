import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DividerModule } from 'primeng/divider';
import { MessageModule } from 'primeng/message';
import { ApiService } from '../core/api.service';
import { getApiErrorMessage } from '../core/api.models';
import { AuthService } from '../core/auth.service';

type JwtPayload = {
  exp?: number;
  jti?: string;
};

type RefreshStatus = {
  rotated: boolean;
  previousExp: string;
  newExp: string;
  previousJti: string;
  newJti: string;
};

@Component({
  selector: 'app-auth-refresh-page',
  standalone: true,
  imports: [CommonModule, RouterModule, ButtonModule, CardModule, DividerModule, MessageModule],
  templateUrl: './auth-refresh-page.component.html',
  styleUrl: './auth-refresh-page.component.scss',
})
export class AuthRefreshPageComponent {
  apiError = '';
  refreshStatus?: RefreshStatus;

  constructor(private readonly api: ApiService, private readonly auth: AuthService) {}

  refreshToken(): void {
    const token = this.auth.getToken();
    if (!token) {
      this.apiError = 'No hay token para refrescar';
      this.refreshStatus = undefined;
      return;
    }

    this.api.refreshToken(token).subscribe({
      next: (response) => {
        if (!response.success || !response.data) {
          this.apiError = response.error?.message || 'Error al refrescar token';
          this.refreshStatus = undefined;
          return;
        }

        const previousToken = token;
        const newToken = response.data.access_token;
        const rotated = previousToken !== newToken;

        this.auth.setToken(newToken);
        this.refreshStatus = {
          rotated,
          previousExp: this.getTokenExpIso(previousToken),
          newExp: this.getTokenExpIso(newToken),
          previousJti: this.getTokenJti(previousToken),
          newJti: this.getTokenJti(newToken),
        };

        this.apiError = rotated
          ? ''
          : 'El servidor devolvio el mismo token. Revisar endpoint de refresh.';
      },
      error: (err) => {
        this.apiError = getApiErrorMessage(err, 'Error al refrescar token');
        this.refreshStatus = undefined;
      },
    });
  }

  private getTokenExpIso(token: string): string {
    const payload = this.parseJwtPayload(token);
    if (!payload || typeof payload.exp !== 'number') {
      return 'N/A';
    }
    return new Date(payload.exp * 1000).toISOString();
  }

  private getTokenJti(token: string): string {
    const payload = this.parseJwtPayload(token);
    if (!payload || typeof payload.jti !== 'string') {
      return 'N/A';
    }
    return payload.jti;
  }

  private parseJwtPayload(token: string): JwtPayload | null {
    const parts = token.split('.');
    if (parts.length !== 3) {
      return null;
    }

    try {
      const base64 = parts[1].replaceAll('-', '+').replaceAll('_', '/');
      const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
      const decoded = atob(padded);
      return JSON.parse(decoded) as JwtPayload;
    } catch {
      return null;
    }
  }
}
