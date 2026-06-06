import { Injectable, computed, signal } from '@angular/core';

interface LayoutState {
  staticMenuDesktopInactive: boolean;
  overlayMenuActive: boolean;
  mobileMenuActive: boolean;
  activePath: string | null;
}

@Injectable({
  providedIn: 'root'
})
export class LayoutService {
  private readonly themeKey = 'onecore_theme';

  layoutState = signal<LayoutState>({
    staticMenuDesktopInactive: false,
    overlayMenuActive: false,
    mobileMenuActive: false,
    activePath: null
  });

  isDesktop = computed(() => window.innerWidth > 991);
  isDarkTheme = signal<boolean>(false);

  constructor() {
    const savedTheme = localStorage.getItem(this.themeKey);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = savedTheme ? savedTheme === 'dark' : prefersDark;

    this.isDarkTheme.set(isDark);
    this.applyTheme(isDark);
  }

  onMenuToggle(): void {
    if (this.isDesktop()) {
      this.layoutState.update((prev) => ({
        ...prev,
        staticMenuDesktopInactive: !prev.staticMenuDesktopInactive
      }));
      return;
    }

    this.layoutState.update((prev) => ({
      ...prev,
      mobileMenuActive: !prev.mobileMenuActive
    }));
  }

  closeMobileMenu(): void {
    this.layoutState.update((prev) => ({
      ...prev,
      mobileMenuActive: false,
      overlayMenuActive: false
    }));
  }

  toggleTheme(): void {
    const next = !this.isDarkTheme();
    this.isDarkTheme.set(next);
    this.applyTheme(next);
    localStorage.setItem(this.themeKey, next ? 'dark' : 'light');
  }

  private applyTheme(isDark: boolean): void {
    document.body.classList.toggle('app-dark', isDark);
    document.documentElement.classList.toggle('app-dark', isDark);
  }
}
