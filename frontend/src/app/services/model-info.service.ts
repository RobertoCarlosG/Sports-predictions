import { HttpClient } from '@angular/common/http';
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, catchError, of, shareReplay, tap, timer } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { environment } from '../../environments/environment';

/** Información mínima del modelo activo (endpoint público). */
export interface PublicModelInfo {
  model_loaded: boolean;
  model_version?: string | null;
  base_version?: string | null;
  is_synthetic?: boolean;
  loaded_at?: string | null;
}

@Injectable({ providedIn: 'root' })
export class ModelInfoService {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  private readonly url = `${environment.apiUrl}/api/v1/model/info`;

  /** Refrescamos cada 5 minutos: la versión rara vez cambia. */
  private static readonly POLL_MS = 5 * 60 * 1000;

  private readonly _info = signal<PublicModelInfo | null>(null);
  readonly info = this._info.asReadonly();

  /** `true` si el modelo activo es el sintético de fallback. */
  readonly isSynthetic = computed<boolean>(() => Boolean(this._info()?.is_synthetic));

  /** Etiqueta corta para footer: "rf-db-v1" o "Modelo no cargado". */
  readonly shortLabel = computed<string>(() => {
    const info = this._info();
    if (!info || !info.model_loaded) {
      return 'Modelo no cargado';
    }
    return info.base_version ?? 'rf-v0';
  });

  private readonly poll$: Observable<PublicModelInfo | null> = timer(0, ModelInfoService.POLL_MS).pipe(
    switchMap(() =>
      this.http.get<PublicModelInfo>(this.url).pipe(
        catchError(() => of<PublicModelInfo | null>(null)),
      ),
    ),
    tap((info) => this._info.set(info)),
    shareReplay({ bufferSize: 1, refCount: false }),
  );

  /** Inicia el polling singleton. Llamar en el shell de la app. */
  start(): void {
    this.poll$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  /** Refresca on-demand (p. ej. tras /admin/model/reload). */
  refreshOnce(): void {
    this.http
      .get<PublicModelInfo>(this.url)
      .pipe(
        catchError(() => of<PublicModelInfo | null>(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((info) => this._info.set(info));
  }
}
