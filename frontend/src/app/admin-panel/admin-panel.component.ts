import { HttpErrorResponse } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { Observable } from 'rxjs';

import { AdminApiService } from '../services/admin-api.service';

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
    MatProgressSpinnerModule,
  ],
  templateUrl: './admin-panel.component.html',
  styleUrl: './admin-panel.component.scss',
})
export class AdminPanelComponent implements OnInit {
  private readonly admin = inject(AdminApiService);

  username = '';
  password = '';
  loginLoading = false;
  loginError: string | null = null;
  /** Si no es null, el API no tiene ADMIN_JWT_SECRET (o falló /auth/ready). */
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

  ngOnInit(): void {
    this.admin.authReady().subscribe({
      next: (r) => {
        this.authReadyLoading = false;
        this.configBanner = r.login_available ? null : (r.detail ?? 'El servidor no tiene configurado el acceso al panel.');
        if (r.login_available) {
          this.admin.checkSession().subscribe({
            next: () => this.refreshStatus(),
            error: () => {
              /* sin cookie o expirada: formulario de login */
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
      this.lastActionError = 'Indica fecha de inicio y fin.';
      return;
    }
    this._run('Iniciando importación en segundo plano…', () =>
      this.admin.backfill(this.backfillStart, this.backfillEnd, true, this.backfillSleep),
    );
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
        this.lastActionMessage = r.message + (r.detail ? ` — ${r.detail}` : '');
        if ('stdout_tail' in r && r.stdout_tail) {
          this.lastActionMessage += ' (ver consola del servidor para detalle completo)';
        }
        void this.refreshStatus();
      },
      error: () => {
        this.busy = false;
        this.lastActionError = 'La operación no se completó. Revisa conexión, permisos o datos en el servidor.';
      },
    });
  }
}
