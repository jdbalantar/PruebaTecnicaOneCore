import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly tokenKey = 'onecore_access_token';
  private readonly expirySkewSeconds = 15;

  setToken(token: string): void {
    try {
      localStorage.setItem(this.tokenKey, token);
    } catch {
      // Ignore storage errors to avoid breaking UX in restricted environments.
    }
  }

  getToken(): string | null {
    try {
      return localStorage.getItem(this.tokenKey);
    } catch {
      return null;
    }
  }

  clearToken(): void {
    try {
      localStorage.removeItem(this.tokenKey);
    } catch {
      // Ignore storage errors.
    }
  }

  logout(): void {
    this.clearToken();
  }

  isLoggedIn(): boolean {
    return this.hasValidToken();
  }

  hasValidToken(): boolean {
    const token = this.getToken();
    if (!token) {
      return false;
    }

    if (this.isTokenExpired(token)) {
      this.clearToken();
      return false;
    }

    return true;
  }

  private isTokenExpired(token: string): boolean {
    const payload = this.parseJwtPayload(token);
    if (!payload) {
      return true;
    }

    const expValue = payload.exp;
    if (typeof expValue !== 'number') {
      return true;
    }

    const nowSeconds = Math.floor(Date.now() / 1000);
    return expValue <= nowSeconds + this.expirySkewSeconds;
  }

  private parseJwtPayload(token: string): { exp?: unknown } | null {
    const parts = token.split('.');
    if (parts.length !== 3) {
      return null;
    }

    try {
      const base64 = parts[1].replaceAll('-', '+').replaceAll('_', '/');
      const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
      const decoded = atob(padded);
      return JSON.parse(decoded) as { exp?: unknown };
    } catch {
      return null;
    }
  }
}
