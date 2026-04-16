import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import type { GameDetail, PredictionOut, TeamOut } from '../models/game';
import type { HistoryGame, MlbSyncRangeResult } from '../models/history';

@Injectable({ providedIn: 'root' })
export class GamesApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/api/v1`;

  listGames(date: string, sync = true): Observable<GameDetail[]> {
    const params = new HttpParams()
      .set('date', date)
      .set('sync', String(sync))
      .set('fetch_details', 'true');
    return this.http.get<GameDetail[]>(`${this.base}/games`, { params });
  }

  getGame(gamePk: number): Observable<GameDetail> {
    return this.http.get<GameDetail>(`${this.base}/games/${gamePk}`);
  }

  refreshWeather(gamePk: number): Observable<GameDetail> {
    return this.http.post<GameDetail>(`${this.base}/games/${gamePk}/weather`, {});
  }

  predict(gamePk: number): Observable<PredictionOut> {
    return this.http.get<PredictionOut>(`${this.base}/predict/${gamePk}`);
  }

  listMlbTeams(): Observable<TeamOut[]> {
    return this.http.get<TeamOut[]>(`${this.base}/mlb/teams`);
  }

  listMlbHistory(params: {
    season?: string;
    team_id?: number;
    from?: string;
    to?: string;
    only_final?: boolean;
    only_with_scores?: boolean;
    limit?: number;
    offset?: number;
  }): Observable<HistoryGame[]> {
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
  }

  syncMlbRange(body: {
    start_date: string;
    end_date: string;
    fetch_details?: boolean;
  }): Observable<MlbSyncRangeResult> {
    return this.http.post<MlbSyncRangeResult>(`${this.base}/mlb/sync-range`, body);
  }
}
