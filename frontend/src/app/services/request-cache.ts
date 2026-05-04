import { Observable, throwError } from 'rxjs';
import { catchError, shareReplay } from 'rxjs/operators';

/**
 * Caché de Observables HTTP por clave (`shareReplay(1)` con TTL).
 *
 * Objetivo: reducir egress de Supabase al volver a una misma vista (Hoy/Mañana/Semana).
 * - Primera llamada con una clave → ejecuta la petición y comparte la respuesta.
 * - Llamadas posteriores dentro del TTL → reciben el último valor sin nueva HTTP.
 * - Errores no se cachean: la entrada se elimina al primer error y la siguiente subscripción
 *   relanza la petición.
 * - `get(..., force=true)` ignora la entrada existente (botón «Reintentar»).
 *
 * No es una caché de respuesta (no clona el payload): si el consumidor muta el objeto
 * recibido, otros suscriptores verán esa mutación. Mantén los datos como solo-lectura.
 */
interface CachedRequest<T> {
  observable: Observable<T>;
  createdAt: number;
}

export interface RequestCacheOptions {
  /** Tiempo de vida en ms; por defecto 60s. Pasa 0 para que la entrada no caduque. */
  ttlMs?: number;
}

export class RequestCache<T> {
  private readonly entries = new Map<string, CachedRequest<T>>();
  private readonly ttlMs: number;

  constructor(options?: RequestCacheOptions) {
    this.ttlMs = options?.ttlMs ?? 60_000;
  }

  /**
   * Devuelve el Observable cacheado para `key`, o crea uno nuevo si no existe / caducó.
   * `force=true` borra la entrada antes de comprobar (uso típico: «Reintentar»).
   */
  get(key: string, factory: () => Observable<T>, force = false): Observable<T> {
    if (force) {
      this.entries.delete(key);
    }
    const now = Date.now();
    const hit = this.entries.get(key);
    if (hit != null && (this.ttlMs === 0 || now - hit.createdAt < this.ttlMs)) {
      return hit.observable;
    }
    const observable = factory().pipe(
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    const entry: CachedRequest<T> = { observable, createdAt: now };
    this.entries.set(key, entry);

    return observable.pipe(
      catchError((err) => {
        if (this.entries.get(key) === entry) {
          this.entries.delete(key);
        }
        return throwError(() => err);
      }),
    );
  }

  invalidate(key: string): void {
    this.entries.delete(key);
  }

  /** Elimina entradas cuya clave cumple `predicate` (para invalidación selectiva). */
  invalidateMatching(predicate: (key: string) => boolean): void {
    for (const k of [...this.entries.keys()]) {
      if (predicate(k)) {
        this.entries.delete(k);
      }
    }
  }

  clear(): void {
    this.entries.clear();
  }
}
