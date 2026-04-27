import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, tap, throwError } from 'rxjs';

import { environment } from '../../environments/environment';

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

export interface AdminSessionResponse {
  username: string;
  token_expires_at?: string | null;
  token_ttl_minutes?: number | null;
  seconds_until_expiry?: number | null;
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
  training_meta?: Record<string, unknown> | null;
}

export interface BacktestSummary {
  n_games: number;
  ml_wins: number;
  ml_losses: number;
  ou_wins: number;
  ou_losses: number;
  ou_pushes: number;
  global_hit_rate_pct: number | null;
  total_decided_picks: number;
  total_correct_picks: number;
}

export interface BacktestTimePoint {
  game_date: string;
  games_count: number;
  ml_hit_rate_pct: number | null;
  ou_hit_rate_pct: number | null;
  ou_decided: number;
}

export interface BacktestGameRow {
  game_pk: number;
  game_date: string;
  game_datetime_utc: string | null;
  away_abbr: string;
  home_abbr: string;
  matchup_label: string;
  p_home: number;
  ml_confidence: number;
  predicted_winner: 'home' | 'away';
  actual_winner: 'home' | 'away' | 'tie';
  ml_correct: boolean;
  over_under_line: number;
  total_runs_estimate: number;
  predicted_ou: 'over' | 'under';
  total_runs_actual: number;
  ou_outcome: 'win' | 'loss' | 'push';
  ou_correct: boolean | null;
  success_count: number;
  success_label: string;
}

export interface BacktestResponse {
  date_from: string;
  date_to: string;
  min_confidence: number;
  skip_empty_days: boolean;
  summary: BacktestSummary;
  timeseries: BacktestTimePoint[];
  games: BacktestGameRow[];
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
   * Comprueba si la cookie de sesión sigue siendo válida (p. ej. al cargar /operations).
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

  /** Renueva el JWT (misma duración TTL); usar durante importaciones largas. */
  refreshSession(): Observable<AdminSessionResponse> {
    return this.http.post<AdminSessionResponse>(`${this.base}/auth/refresh`, {}, this.opts());
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
    max_depth?: number;
    min_samples_leaf?: number;
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

  getBacktestReport(params: {
    dateFrom: string;
    dateTo: string;
    minConfidence: number;
    skipEmptyDays: boolean;
  }): Observable<BacktestResponse> {
    let httpParams = new HttpParams()
      .set('date_from', params.dateFrom)
      .set('date_to', params.dateTo)
      .set('min_confidence', String(params.minConfidence))
      .set('skip_empty_days', String(params.skipEmptyDays));
    return this.http.get<BacktestResponse>(`${this.base}/predictions/backtest`, {
      ...this.opts(),
      params: httpParams,
    });
  }
}
