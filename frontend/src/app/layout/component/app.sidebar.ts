import { Component, HostListener, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AppMenu } from './app.menu';
import { LayoutService } from '../service/layout.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [AppMenu],
  template: `
    <div class="layout-sidebar">
      <app-menu></app-menu>
    </div>
  `
})
export class AppSidebar {
  private readonly layout = inject(LayoutService);
  private readonly router = inject(Router);

  constructor() {
    this.router.events.subscribe(() => this.layout.closeMobileMenu());
  }

  @HostListener('window:resize')
  onResize(): void {
    if (window.innerWidth > 991) {
      this.layout.closeMobileMenu();
    }
  }
}
