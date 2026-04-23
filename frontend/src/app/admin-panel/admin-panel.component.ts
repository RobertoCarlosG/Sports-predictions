import { HttpErrorResponse } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { Observable, Subscription, interval } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

import {
  AdminApiService,
  type BackfillJobStatusResponse,
} from '../services/admin-api.service';
import { AdminOpResultData, AdminOpResultDialogComponent } from './admin-op-result-dialog.component';

@Component({
  selector: 'app-admin-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './admin-panel.component.html',
  styleUrl: './admin-panel.component.scss',
})
export class AdminPanelComponent implements OnInit, OnDestroy {
  private readonly admin = inject(AdminApiService);
  private readonly dialog = inject(MatDialog);

  private backfillPollSub: Subscription | null = null;

  username = '';
  password = '';
  hidePassword = true;
  loginLoading = false;
  loginError: string | null = null;
  configBanner: string | null = null;
  authReadyLoading = true;

  statusText: string | null = null;
  statusDetail: string | null = null;
  lastActionMessage: string | null = null;
  lastActionError: string | null = null;
  busy = false;

  backfillStart = '';
  backfillEnd = '';
  backfillSleep = 0.3;
  seasonFilter = '';
  snapshotWindow = 10;
  trainValFrom = '';
  trainSeason = '';
  trainModelVersion = 'rf-db-v1';

  /** Seguimiento de importación en segundo plano. */
  backfillTracking = false;
  backfillStatus: BackfillJobStatusResponse | null = null;
  private pendingBackfillJobId: string | null = null;
  backfillTaskLabel = '';

  ngOnInit(): void {
    this.admin.authReady().subscribe({
      next: (r) => {
        this.authReadyLoading = false;
        this.configBanner = r.login_available ? null : (r.detail ?? 'El servidor no tiene configurado el acceso al panel.');
        if (r.login_available) {
          this.admin.checkSession().subscribe({
            next: () => {
              void this.refreshStatus();
              this.tryResumeBackfillPoll();
            },
            error: () => {
              /* sin sesión */
            },
          });
        }
      },
      error: () => {
        this.authReadyLoading = false;
        this.configBanner = 'No se pudo contactar al API o comprobar la configuración.';
      },
    });
  }

  ngOnDestroy(): void {
    this.stopBackfillPoll();
  }

  get operationsLocked(): boolean {
    return this.busy || this.backfillTracking;
  }

  get backfillProgressPercent(): number {
    const t = this.backfillStatus?.days_total ?? 0;
    const d = this.backfillStatus?.days_done ?? 0;
    if (t <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((d / t) * 100));
  }

  get backfillPhaseLabel(): string {
    const s = this.backfillStatus?.status;
    if (s === 'queued') {
      return 'En cola…';
    }
    if (s === 'running') {
      return 'Sincronizando fechas con la API de MLB…';
    }
    return '';
  }

  loggedIn(): boolean {
    return this.admin.isLoggedIn();
  }

  login(): void {
    this.loginLoading = true;
    this.loginError = null;
    this.admin.login(this.username, this.password).subscribe({
      next: () => {
        this.loginLoading = false;
        this.password = '';
        void this.refreshStatus();
        this.tryResumeBackfillPoll();
      },
      error: (err: unknown) => {
        this.loginLoading = false;
        if (err instanceof HttpErrorResponse) {
          const raw = err.error;
          if (raw && typeof raw === 'object') {
            const o = raw as { message?: unknown; detail?: unknown };
            const msg = o.message != null ? String(o.message).trim() : '';
            const det = o.detail != null ? String(o.detail).trim() : '';
            if (err.status === 503) {
              if (msg) {
                this.loginError = msg;
                return;
              }
              if (det === 'database_schema_missing') {
                this.loginError =
                  'La base de datos no tiene las tablas necesarias (p. ej. admin_users). Ejecuta en Supabase/Postgres el script backend/sql/002_prediction_cache_and_admin.sql.';
                return;
              }
              if (det) {
                this.loginError = det;
                return;
              }
            }
          }
        }
        this.loginError = 'No se pudo iniciar sesión. Revisa usuario y contraseña.';
      },
    });
  }

  logout(): void {
    this.stopBackfillPoll();
    this.backfillTracking = false;
    this.pendingBackfillJobId = null;
    this.admin.logout().subscribe({
      next: () => {
        this.statusText = null;
        this.statusDetail = null;
        this.lastActionMessage = null;
        this.lastActionError = null;
      },
      error: () => {
        this.admin.clearSessionLocal();
        this.statusText = null;
        this.statusDetail = null;
        this.lastActionMessage = null;
        this.lastActionError = null;
      },
    });
  }

  refreshStatus(): void {
    this.lastActionError = null;
    this.admin.status().subscribe({
      next: (r) => {
        this.statusText = r.message;
        this.statusDetail = r.detail;
      },
      error: () => {
        this.lastActionError = 'No se pudo leer el estado. Tu sesión puede haber expirado.';
      },
    });
  }

  rebuildSnapshots(): void {
    this._run('Recalculando indicadores…', () =>
      this.admin.rebuildSnapshots(this.seasonFilter.trim() || null, this.snapshotWindow),
    );
  }

  clearCache(): void {
    this._run('Vaciando caché…', () => this.admin.clearPredictionCache());
  }

  reloadModel(): void {
    this._run('Recargando modelo…', () => this.admin.reloadModel());
  }

  train(): void {
    this._run('Entrenando (puede tardar varios minutos)…', () =>
      this.admin.trainModel({
        season: this.trainSeason.trim() || null,
        val_from: this.trainValFrom.trim() || null,
        model_version: this.trainModelVersion.trim() || 'rf-db-v1',
      }),
    );
  }

  backfill(): void {
    if (!this.backfillStart || !this.backfillEnd) {
      this.openResultDialog({
        title: 'Importación',
        message: 'Indica fecha de inicio y fin.',
        technicalDetail: null,
        success: false,
      });
      return;
    }
    if (this.backfillTracking) {
      return;
    }
    this.busy = true;
    this.lastActionError = null;
    this.lastActionMessage = 'Enviando importación al servidor…';
    this.admin.backfill(this.backfillStart, this.backfillEnd, true, this.backfillSleep).subscribe({
      next: (r) => {
        this.busy = false;
        this.lastActionMessage = null;
        this.pendingBackfillJobId = r.job_id ?? null;
        this.backfillTaskLabel = `Importación MLB (${this.backfillStart} → ${this.backfillEnd})`;
        this.startBackfillPoll();
      },
      error: (err: unknown) => {
        this.busy = false;
        this.lastActionMessage = null;
        this.openResultDialogFromHttp(err, 'Importación');
      },
    });
  }

  private tryResumeBackfillPoll(): void {
    if (!this.admin.isLoggedIn()) {
      return;
    }
    this.admin.getBackfillStatus().subscribe({
      next: (s) => {
        if ((s.status === 'queued' || s.status === 'running') && s.job_id) {
          this.pendingBackfillJobId = s.job_id;
          this.backfillTaskLabel = `Importación MLB (${s.date_start ?? '?'} → ${s.date_end ?? '?'})`;
          this.backfillStatus = s;
          this.startBackfillPoll();
        }
      },
      error: () => {
        /* ignorar */
      },
    });
  }

  private startBackfillPoll(): void {
    this.stopBackfillPoll();
    this.backfillTracking = true;
    this.backfillPollSub = interval(2000)
      .pipe(
        startWith(0),
        switchMap(() => this.admin.getBackfillStatus()),
      )
      .subscribe({
        next: (s) => {
          this.backfillStatus = s;
          if (!this.pendingBackfillJobId || s.job_id !== this.pendingBackfillJobId) {
            return;
          }
          if (s.status === 'success' || s.status === 'error') {
            this.stopBackfillPoll();
            this.backfillTracking = false;
            const ok = s.status === 'success';
            this.openResultDialog({
              title: ok ? 'Importación terminada' : 'Importación fallida',
              message: ok
                ? (s.result_message ?? 'Proceso completado.')
                : 'La importación falló. Pasa el cursor sobre el icono de información para ver el error del servidor.',
              technicalDetail: ok ? null : s.error_detail,
              success: ok,
            });
            this.pendingBackfillJobId = null;
            void this.refreshStatus();
          }
        },
        error: () => {
          this.stopBackfillPoll();
          this.backfillTracking = false;
          this.pendingBackfillJobId = null;
          this.openResultDialog({
            title: 'Importación',
            message: 'No se pudo leer el estado de la importación (red o sesión).',
            technicalDetail: null,
            success: false,
          });
        },
      });
  }

  private stopBackfillPoll(): void {
    this.backfillPollSub?.unsubscribe();
    this.backfillPollSub = null;
  }

  private _run(
    label: string,
    op: () => Observable<{ message: string; detail?: string | null; stdout_tail?: string | null }>,
  ): void {
    this.busy = true;
    this.lastActionMessage = label;
    this.lastActionError = null;
    op().subscribe({
      next: (r) => {
        this.busy = false;
        const line = r.message + (r.detail ? ` — ${r.detail}` : '');
        this.lastActionMessage = line;
        const tech =
          'stdout_tail' in r && r.stdout_tail
            ? String(r.stdout_tail)
            : r.detail
              ? String(r.detail)
              : null;
        this.openResultDialog({
          title: 'Operación completada',
          message: line,
          technicalDetail: tech,
          success: true,
        });
        void this.refreshStatus();
      },
      error: (err: unknown) => {
        this.busy = false;
        this.openResultDialogFromHttp(err, 'Operación');
      },
    });
  }

  private openResultDialog(data: AdminOpResultData): void {
    this.dialog.open(AdminOpResultDialogComponent, {
      width: 'min(96vw, 440px)',
      autoFocus: 'dialog',
      data,
    });
  }

  private openResultDialogFromHttp(err: unknown, title: string): void {
    if (err instanceof HttpErrorResponse) {
      const raw = err.error;
      let message = `Error HTTP ${err.status}`;
      let technical: string | null = null;
      if (raw && typeof raw === 'object') {
        const o = raw as { message?: unknown; detail?: unknown; technical?: unknown };
        if (o.message != null) {
          message = String(o.message);
        } else if (o.detail != null) {
          message = String(o.detail);
        }
        if (o.technical != null) {
          technical = String(o.technical);
        }
      }
      this.openResultDialog({ title, message, technicalDetail: technical, success: false });
      return;
    }
    this.openResultDialog({
      title,
      message: 'Error inesperado',
      technicalDetail: err instanceof Error ? err.message : String(err),
      success: false,
    });
  }
}
