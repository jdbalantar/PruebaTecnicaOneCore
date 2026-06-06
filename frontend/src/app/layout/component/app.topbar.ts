import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { Router, RouterModule } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { AuthService } from '../../core/auth.service';
import { LayoutService } from '../service/layout.service';

@Component({
  selector: 'app-topbar',
  standalone: true,
  imports: [CommonModule, RouterModule, ButtonModule],
  template: `
    <div class="layout-topbar">
      <div class="layout-topbar-logo-container">
        <a class="layout-topbar-logo" routerLink="/app">
          <i class="pi pi-building text-primary"></i>
          <span>OneCore App</span>
        </a>
      </div>

      <div class="layout-topbar-menu-content">
        <button type="button" class="layout-topbar-action" routerLink="/app">
          <i class="pi pi-home"></i>
          <span>Home</span>
        </button>
        <button type="button" class="layout-topbar-action" (click)="layout.toggleTheme()">
          <i class="pi" [ngClass]="layout.isDarkTheme() ? 'pi-sun' : 'pi-moon'"></i>
          <span>{{ layout.isDarkTheme() ? 'Light' : 'Dark' }}</span>
        </button>
        <button type="button" class="layout-topbar-action" (click)="logout()">
          <i class="pi pi-sign-out"></i>
          <span>Salir</span>
        </button>
      </div>
    </div>
  `
})
export class AppTopbar {
  layout = inject(LayoutService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  logout(): void {
    this.auth.clearToken();
    void this.router.navigate(['/login']);
  }
}
