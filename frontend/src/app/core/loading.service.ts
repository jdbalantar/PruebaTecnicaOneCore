import { Injectable, computed, signal } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class LoadingService {
  private readonly showDelayMs = 180;
  private readonly pendingRequests = signal(0);
  private readonly loadingVisible = signal(false);
  private showTimer: ReturnType<typeof setTimeout> | null = null;

  readonly isLoading = computed(() => this.loadingVisible());

  begin(): void {
    this.pendingRequests.update((value) => {
      const nextValue = value + 1;

      if (nextValue === 1 && !this.loadingVisible()) {
        this.scheduleShow();
      }

      return nextValue;
    });
  }

  end(): void {
    this.pendingRequests.update((value) => {
      const nextValue = value > 0 ? value - 1 : 0;

      if (nextValue === 0) {
        this.clearShowTimer();
        this.loadingVisible.set(false);
      }

      return nextValue;
    });
  }

  private scheduleShow(): void {
    this.clearShowTimer();
    this.showTimer = setTimeout(() => {
      this.showTimer = null;
      if (this.pendingRequests() > 0) {
        this.loadingVisible.set(true);
      }
    }, this.showDelayMs);
  }

  private clearShowTimer(): void {
    if (this.showTimer !== null) {
      clearTimeout(this.showTimer);
      this.showTimer = null;
    }
  }
}
