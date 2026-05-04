import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import type { GameDetail, GamesListResponse, PredictionOut, TeamOut } from '../models/game';
import type { HistoryGame, MlbSyncRangeResult } from '../models/history';
import { RequestCache } from './request-cache';

/** Filtros de `listMlbHistory`. Aceptados también por la clave de caché. */
interface ListMlbHistoryParams {
  season?: string;
  team_id?: number;
  from?: string;
  to?: string;
  only_final?: boolean;
  only_with_scores?: boolean;
  limit?: number;
  offset?: number;
}

@Injectable({ providedIn: 'root' })
export class GamesApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/api/v1`;

  /**
   * Caches a nivel de servicio (`shareReplay(1)` con TTL).
   * Sobreviven a la navegación entre rutas y evitan hits a Supabase al alternar
   * Hoy → Mañana → Hoy. TTLs cortos en datos «vivos», más larga en lo estable.
   */
  private readonly listGamesCache = new RequestCache<GamesListResponse>({ ttlMs: 60_000 });
  private readonly gameCache = new RequestCache<GameDetail>({ ttlMs: 60_000 });
  private readonly predictCache = new RequestCache<PredictionOut>({ ttlMs: 60_000 });
  private readonly teamsCache = new RequestCache<TeamOut[]>({ ttlMs: 3_600_000 });
  private readonly historyCache = new RequestCache<HistoryGame[]>({ ttlMs: 300_000 });

  listGames(
    date: string,
    sync = true,
    options?: { includePredictions?: boolean; force?: boolean },
  ): Observable<GamesListResponse> {
    const includePredictions = options?.includePredictions !== false;
    const key = `${date}|sync=${sync}|p=${includePredictions}`;
    return this.listGamesCache.get(
      key,
      () => {
        const params = new HttpParams()
          .set('date', date)
          .set('sync', String(sync))
          .set('fetch_details', 'true')
          .set('include_predictions', String(includePredictions));
        return this.http.get<GamesListResponse>(`${this.base}/games`, { params });
      },
      options?.force === true,
    );
  }

  getGame(
    gamePk: number,
    options?: { includePredictions?: boolean; force?: boolean },
  ): Observable<GameDetail> {
    const include = options?.includePredictions !== false;
    const key = `${gamePk}|p=${include}`;
    return this.gameCache.get(
      key,
      () =>
        this.http.get<GameDetail>(`${this.base}/games/${gamePk}`, {
          params: new HttpParams().set('include_predictions', String(include)),
        }),
      options?.force === true,
    );
  }

  refreshWeather(gamePk: number): Observable<GameDetail> {
    return this.http.post<GameDetail>(`${this.base}/games/${gamePk}/weather`, {}).pipe(
      tap(() => this.invalidateGame(gamePk)),
    );
  }

  predict(gamePk: number, options?: { force?: boolean }): Observable<PredictionOut> {
    return this.predictCache.get(
      String(gamePk),
      () => this.http.get<PredictionOut>(`${this.base}/predict/${gamePk}`),
      options?.force === true,
    );
  }

  /** Recalcula la estimación en el servidor (por si el proceso automático no actualizó a tiempo). */
  refreshPrediction(gamePk: number): Observable<PredictionOut> {
    return this.http.post<PredictionOut>(`${this.base}/predict/${gamePk}/refresh`, {}).pipe(
      tap(() => this.invalidatePrediction(gamePk)),
    );
  }

  listMlbTeams(options?: { force?: boolean }): Observable<TeamOut[]> {
    return this.teamsCache.get(
      'all',
      () => this.http.get<TeamOut[]>(`${this.base}/mlb/teams`),
      options?.force === true,
    );
  }

  listMlbHistory(
    params: ListMlbHistoryParams,
    options?: { force?: boolean },
  ): Observable<HistoryGame[]> {
    const key = this.buildHistoryKey(params);
    return this.historyCache.get(
      key,
      () => {
        let hp = new HttpParams();
        if (params.season) {
          hp = hp.set('season', params.season);
        }
        if (params.team_id != null) {
          hp = hp.set('team_id', String(params.team_id));
        }
        if (params.from) {
          hp = hp.set('from', params.from);
        }
        if (params.to) {
          hp = hp.set('to', params.to);
        }
        if (params.only_final) {
          hp = hp.set('only_final', 'true');
        }
        if (params.only_with_scores) {
          hp = hp.set('only_with_scores', 'true');
        }
        if (params.limit != null) {
          hp = hp.set('limit', String(params.limit));
        }
        if (params.offset != null) {
          hp = hp.set('offset', String(params.offset));
        }
        return this.http.get<HistoryGame[]>(`${this.base}/mlb/history/games`, { params: hp });
      },
      options?.force === true,
    );
  }

  syncMlbRange(body: {
    start_date: string;
    end_date: string;
    fetch_details?: boolean;
  }): Observable<MlbSyncRangeResult> {
    return this.http.post<MlbSyncRangeResult>(`${this.base}/mlb/sync-range`, body).pipe(
      tap(() => {
        this.listGamesCache.clear();
        this.predictCache.clear();
        this.gameCache.clear();
        this.historyCache.clear();
      }),
    );
  }

  /** Sincroniza un solo partido desde MLB (schedule + linescore; opcional boxscore/live). */
  syncMlbGame(gamePk: number, fetchDetails = true): Observable<GameDetail> {
    return this.http
      .post<GameDetail>(`${this.base}/mlb/games/${gamePk}/sync`, { fetch_details: fetchDetails })
      .pipe(
        tap(() => {
          this.invalidateGame(gamePk);
          this.invalidatePrediction(gamePk);
          this.listGamesCache.clear();
        }),
      );
  }

  /** Invalida cachés relacionados con un partido (al refrescar tras una mutación). */
  invalidateGame(gamePk: number): void {
    const prefix = `${gamePk}|`;
    this.gameCache.invalidateMatching((k) => k.startsWith(prefix));
    this.listGamesCache.clear();
  }

  invalidatePrediction(gamePk: number): void {
    this.predictCache.invalidate(String(gamePk));
    this.listGamesCache.clear();
  }

  /** Útil tras logout / recarga manual: vacía toda la caché del servicio. */
  clearAllCaches(): void {
    this.listGamesCache.clear();
    this.gameCache.clear();
    this.predictCache.clear();
    this.teamsCache.clear();
    this.historyCache.clear();
  }

  private buildHistoryKey(p: ListMlbHistoryParams): string {
    return JSON.stringify({
      season: p.season ?? null,
      team_id: p.team_id ?? null,
      from: p.from ?? null,
      to: p.to ?? null,
      only_final: !!p.only_final,
      only_with_scores: !!p.only_with_scores,
      limit: p.limit ?? null,
      offset: p.offset ?? null,
    });
  }
}
