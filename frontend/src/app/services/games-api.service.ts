import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import type { GameDetail, PredictionOut } from '../models/game';

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
}
