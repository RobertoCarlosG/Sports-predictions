import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, tap, throwError } from 'rxjs';

import { environment } from '../../environments/environment';

export interface AdminSessionResponse {
  username: string;
}

/** Respuesta de GET /admin/auth/ready (público). */
export interface AdminAuthReadyResponse {
  login_available: boolean;
  detail: string | null;
  jwt_configured?: boolean;
  admin_table_reachable?: boolean;
}

export interface MessageResponse {
  message: string;
  detail: string | null;
  job_id?: string | null;
}

export interface BackfillJobStatusResponse {
  status: string;
  job_id: string | null;
  started_at: number | null;
  finished_at: number | null;
  date_start: string | null;
  date_end: string | null;
  days_total: number;
  days_done: number;
  current_date: string | null;
  error_detail: string | null;
  result_message: string | null;
}

export interface TrainResultResponse {
  message: string;
  stdout_tail: string | null;
}

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/api/v1/admin`;

  /** Indica si la última comprobación local considera sesión válida (cookie HttpOnly). */
  private sessionOk = false;

  private opts(): { withCredentials: boolean } {
    return { withCredentials: true };
  }

  /** Sin cookie: indica si el API tiene ADMIN_JWT_SECRET (si no, login devuelve 503). */
  authReady(): Observable<AdminAuthReadyResponse> {
    return this.http.get<AdminAuthReadyResponse>(`${this.base}/auth/ready`);
  }

  isLoggedIn(): boolean {
    return this.sessionOk;
  }

  /** Marca sesión como cerrada en cliente sin llamar al servidor (p. ej. error de red en logout). */
  clearSessionLocal(): void {
    this.sessionOk = false;
  }

  /**
   * Comprueba si la cookie de sesión sigue siendo válida (p. ej. al cargar /mlb/operaciones).
   */
  checkSession(): Observable<AdminSessionResponse> {
    return this.http.get<AdminSessionResponse>(`${this.base}/auth/me`, this.opts()).pipe(
      tap(() => {
        this.sessionOk = true;
      }),
      catchError((err) => {
        this.sessionOk = false;
        return throwError(() => err);
      }),
    );
  }

  logout(): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.base}/auth/logout`, {}, this.opts()).pipe(
      tap(() => {
        this.sessionOk = false;
      }),
    );
  }

  login(username: string, password: string): Observable<AdminSessionResponse> {
    return this.http
      .post<AdminSessionResponse>(`${this.base}/auth/login`, { username, password }, this.opts())
      .pipe(
        tap(() => {
          this.sessionOk = true;
        }),
      );
  }

  status(): Observable<MessageResponse> {
    return this.http.get<MessageResponse>(`${this.base}/status`, this.opts());
  }

  rebuildSnapshots(season: string | null, window: number): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(
      `${this.base}/pipeline/rebuild-snapshots`,
      { season: season || null, window },
      this.opts(),
    );
  }

  clearPredictionCache(): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.base}/pipeline/clear-prediction-cache`, {}, this.opts());
  }

  reloadModel(): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.base}/model/reload`, {}, this.opts());
  }

  trainModel(body: {
    output?: string | null;
    season?: string | null;
    val_from?: string | null;
    model_version?: string;
    trees?: number;
  }): Observable<TrainResultResponse> {
    return this.http.post<TrainResultResponse>(`${this.base}/pipeline/train`, body, this.opts());
  }

  backfill(start: string, end: string, fetchDetails: boolean, sleepS: number): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(
      `${this.base}/pipeline/backfill`,
      { start, end, fetch_details: fetchDetails, sleep_s: sleepS },
      this.opts(),
    );
  }

  getBackfillStatus(): Observable<BackfillJobStatusResponse> {
    return this.http.get<BackfillJobStatusResponse>(`${this.base}/pipeline/backfill-status`, this.opts());
  }
}
