import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, tap, throwError } from 'rxjs';

import { environment } from '../../environments/environment';

export interface UserAuthReadyResponse {
  login_available: boolean;
  detail: string | null;
  jwt_configured?: boolean;
  google_configured?: boolean;
  email_login_available?: boolean;
  app_users_table_reachable?: boolean;
}

export interface UserSessionResponse {
  user_id: string;
  email: string;
  display_name?: string | null;
  picture_url?: string | null;
  token_expires_at?: string | null;
  token_ttl_minutes?: number | null;
  seconds_until_expiry?: number | null;
}

@Injectable({ providedIn: 'root' })
export class UserAuthService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/api/v1/auth`;

  private sessionOk = false;

  private opts(): { withCredentials: true; headers: Record<string, string> } {
    return {
      withCredentials: true,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    };
  }

  authReady(): Observable<UserAuthReadyResponse> {
    return this.http.get<UserAuthReadyResponse>(`${this.base}/ready`);
  }

  isLoggedIn(): boolean {
    return this.sessionOk;
  }

  clearSessionLocal(): void {
    this.sessionOk = false;
  }

  checkSession(): Observable<UserSessionResponse> {
    return this.http.get<UserSessionResponse>(`${this.base}/me`, this.opts()).pipe(
      tap(() => {
        this.sessionOk = true;
      }),
      catchError((err) => {
        this.sessionOk = false;
        return throwError(() => err);
      }),
    );
  }

  loginEmail(email: string, password: string): Observable<UserSessionResponse> {
    return this.http
      .post<UserSessionResponse>(`${this.base}/login`, { email, password }, this.opts())
      .pipe(tap(() => (this.sessionOk = true)));
  }

  registerEmail(email: string, password: string, displayName?: string): Observable<UserSessionResponse> {
    return this.http
      .post<UserSessionResponse>(
        `${this.base}/register`,
        { email, password, display_name: displayName ?? null },
        this.opts(),
      )
      .pipe(tap(() => (this.sessionOk = true)));
  }

  logout(): Observable<{ message: string; detail: string }> {
    return this.http.post<{ message: string; detail: string }>(`${this.base}/logout`, {}, this.opts()).pipe(
      tap(() => {
        this.sessionOk = false;
      }),
    );
  }

  /** Navegación completa: el servidor redirige a Google y vuelve con cookie HttpOnly. */
  startGoogleLogin(): void {
    this.redirectTo(`${this.base}/google`);
  }

  /** Indirección sobre window.location para poder testear sin navegar el runner. */
  protected redirectTo(url: string): void {
    window.location.href = url;
  }
}
