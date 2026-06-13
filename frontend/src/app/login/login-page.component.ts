import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { UserAuthService, type UserAuthReadyResponse } from '../services/user-auth.service';

type Mode = 'login' | 'register';

@Component({
  selector: 'app-login-page',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './login-page.component.html',
  styleUrl: './login-page.component.scss',
})
export class LoginPageComponent implements OnInit {
  private readonly auth = inject(UserAuthService);
  private readonly router = inject(Router);

  mode = signal<Mode>('login');
  loading = signal(false);
  checkingSession = signal(true);
  authConfig = signal<UserAuthReadyResponse | null>(null);

  email = '';
  password = '';
  displayName = '';
  hidePassword = true;
  error = signal<string | null>(null);

  ngOnInit(): void {
    // Si ya hay sesión activa, redirigir directamente
    if (this.auth.isLoggedIn()) {
      void this.router.navigate([this.redirectTarget()]);
      return;
    }
    this.auth.checkSession().subscribe({
      next: () => {
        void this.router.navigate([this.redirectTarget()]);
      },
      error: () => {
        this.checkingSession.set(false);
        this.loadAuthConfig();
      },
    });
  }

  private loadAuthConfig(): void {
    this.auth.authReady().subscribe({
      next: (r) => this.authConfig.set(r),
      error: () => this.authConfig.set({ login_available: false, detail: null }),
    });
  }

  private redirectTarget(): string {
    // Intenta leer el parámetro ?next= de la URL actual
    const params = new URLSearchParams(window.location.search);
    const next = params.get('next');
    return next && next.startsWith('/') ? next : '/bets';
  }

  toggleMode(): void {
    this.mode.update((m) => (m === 'login' ? 'register' : 'login'));
    this.error.set(null);
    this.password = '';
  }

  submitEmail(): void {
    this.error.set(null);
    if (!this.email.trim() || !this.password) {
      this.error.set('Completa todos los campos.');
      return;
    }
    this.loading.set(true);

    const obs =
      this.mode() === 'login'
        ? this.auth.loginEmail(this.email.trim(), this.password)
        : this.auth.registerEmail(this.email.trim(), this.password, this.displayName.trim() || undefined);

    obs.subscribe({
      next: () => {
        void this.router.navigate([this.redirectTarget()]);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(this.extractError(err));
      },
    });
  }

  loginGoogle(): void {
    this.auth.startGoogleLogin();
  }

  private extractError(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      const body = err.error;
      if (body && typeof body === 'object') {
        const o = body as { detail?: unknown; message?: unknown };
        if (typeof o.detail === 'string') return o.detail;
        if (typeof o.message === 'string') return o.message;
      }
      if (err.status === 409) return 'Ya existe una cuenta con ese email.';
      if (err.status === 401) return 'Email o contraseña incorrectos.';
      if (err.status === 503) return 'El servidor no está configurado aún.';
    }
    return 'Ocurrió un error. Inténtalo de nuevo.';
  }

  get googleAvailable(): boolean {
    return this.authConfig()?.google_configured ?? false;
  }

  get emailAvailable(): boolean {
    return this.authConfig()?.email_login_available ?? false;
  }
}
