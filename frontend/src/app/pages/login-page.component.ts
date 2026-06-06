import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { MessageModule } from 'primeng/message';
import { PasswordModule } from 'primeng/password';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { getApiErrorMessage } from '../core/api.models';

@Component({
  selector: 'app-login-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CardModule,
    ButtonModule,
    AutoCompleteModule,
    PasswordModule,
    MessageModule
  ],
  templateUrl: './login-page.component.html',
  styleUrl: './login-page.component.scss'
})
export class LoginPageComponent implements OnInit {
  usernameSuggestions: string[] = [];

  username = 'admin';
  password = '';
  loading = false;
  error = '';
  submitted = false;

  private returnUrl = '/app';

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    const requestedReturnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
    this.returnUrl = this.resolveSafeReturnUrl(requestedReturnUrl);

    if (this.auth.hasValidToken()) {
      void this.router.navigate([this.returnUrl]);
    }
  }

  submit(form: NgForm): void {
    this.submitted = true;
    this.error = '';

    if (form.invalid || this.usernameError || this.passwordError) {
      Object.values(form.controls).forEach((control) => control.markAsTouched());
      return;
    }

    this.loading = true;

    this.api.login({ username: this.username, password: this.password }).subscribe({
      next: (response) => {
        if (!response.success || !response.data) {
          this.error = response.error?.message || 'No se pudo iniciar sesion';
          return;
        }

        this.auth.setToken(response.data.access_token);
        void this.router.navigate([this.returnUrl]);
      },
      error: (err) => {
        this.error = getApiErrorMessage(err, 'No se pudo iniciar sesion');
        this.loading = false;
      },
      complete: () => {
        this.loading = false;
      }
    });
  }

  get usernameError(): string {
    const value = this.username.trim();
    if (!value) {
      return 'El usuario es obligatorio.';
    }
    if (value.length < 3) {
      return 'El usuario debe tener al menos 3 caracteres.';
    }
    return '';
  }

  get passwordError(): string {
    const value = this.password;
    if (!value) {
      return 'La contrasena es obligatoria.';
    }
    if (value.length < 8) {
      return 'La contrasena debe tener al menos 8 caracteres.';
    }
    return '';
  }

  get shouldShowUsernameError(): boolean {
    return this.submitted && !!this.usernameError;
  }

  get shouldShowPasswordError(): boolean {
    return this.submitted && !!this.passwordError;
  }

  onUsernameChange(): void {
    this.clearError();
  }

  filterUsername(event: { query: string }): void {
    const query = (event.query || '').toLowerCase();
    const candidates = ['admin', 'uploader'];
    this.usernameSuggestions = candidates.filter((item) => item.includes(query));
  }

  onPasswordChange(): void {
    this.clearError();
  }

  private clearError(): void {
    if (this.error) {
      this.error = '';
    }
  }

  private resolveSafeReturnUrl(value: string | null): string {
    if (!value) {
      return '/app';
    }

    if (!value.startsWith('/app')) {
      return '/app';
    }

    return value;
  }
}
