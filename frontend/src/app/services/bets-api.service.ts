import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export interface BetBankOut {
  id: number;
  name: string;
  initial_amount: number;
  currency: string;
  is_active: boolean;
  created_at: string;
}

export interface BetPeriodOut {
  id: number;
  bank_id: number;
  name: string;
  year: number;
  month: number;
  starting_balance: number;
  closing_balance: number | null;
  status: string;
  closed_at: string | null;
  created_at: string;
}

export interface BetPeriodStatsOut {
  period_id: number;
  name: string;
  starting_balance: number;
  closing_balance: number | null;
  status: string;
  total_stake: number;
  realized_pnl: number;
  roi_pct: number | null;
  decided_bets: number;
  wins: number;
  losses: number;
  pushes: number;
  pending: number;
  win_rate_ml_pct: number | null;
  win_rate_ou_pct: number | null;
}

export interface BetOut {
  id: number;
  bank_id: number;
  period_id: number;
  game_pk: number;
  bet_type: string;
  bet_side: string;
  stake: number;
  odds: number;
  ou_line: number | null;
  status: string;
  result_source: string | null;
  result_checked_at: string | null;
  notes: string | null;
  created_at: string;
  realized_profit: number | null;
}

export interface BetsStatsOut {
  total_stake: number;
  realized_pnl: number;
  roi_pct: number | null;
  decided_bets: number;
  wins: number;
  losses: number;
  pushes: number;
  pending: number;
  by_type: Record<string, Record<string, number | null>>;
}

@Injectable({ providedIn: 'root' })
export class BetsApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/api/v1/bets`;

  private opts(): { withCredentials: true; headers: Record<string, string> } {
    return {
      withCredentials: true,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    };
  }

  listBanks(): Observable<BetBankOut[]> {
    return this.http.get<BetBankOut[]>(`${this.base}/banks`, this.opts());
  }

  createBank(body: { name: string; initial_amount: number; currency?: string }): Observable<BetBankOut> {
    return this.http.post<BetBankOut>(`${this.base}/banks`, body, this.opts());
  }

  updateBank(bankId: number, body: { name?: string; is_active?: boolean }): Observable<BetBankOut> {
    return this.http.put<BetBankOut>(`${this.base}/banks/${bankId}`, body, this.opts());
  }

  listPeriods(bankId?: number, year?: number): Observable<BetPeriodOut[]> {
    let p = new HttpParams();
    if (bankId != null) p = p.set('bank_id', String(bankId));
    if (year != null) p = p.set('year', String(year));
    return this.http.get<BetPeriodOut[]>(`${this.base}/periods`, { ...this.opts(), params: p });
  }

  createPeriod(body: { bank_id: number; year: number; month: number }): Observable<BetPeriodOut> {
    return this.http.post<BetPeriodOut>(`${this.base}/periods`, body, this.opts());
  }

  closePeriod(periodId: number): Observable<BetPeriodOut> {
    return this.http.post<BetPeriodOut>(`${this.base}/periods/${periodId}/close`, {}, this.opts());
  }

  periodStats(periodId: number): Observable<BetPeriodStatsOut> {
    return this.http.get<BetPeriodStatsOut>(`${this.base}/periods/${periodId}/stats`, this.opts());
  }

  exportPeriod(periodId: number): Observable<Blob> {
    return this.http.get(`${this.base}/periods/${periodId}/export`, {
      ...this.opts(),
      responseType: 'blob',
    });
  }

  listBets(params: {
    bank_id?: number;
    period_id?: number;
    game_pk?: number;
    status?: string;
  }): Observable<BetOut[]> {
    let p = new HttpParams();
    if (params.bank_id != null) p = p.set('bank_id', String(params.bank_id));
    if (params.period_id != null) p = p.set('period_id', String(params.period_id));
    if (params.game_pk != null) p = p.set('game_pk', String(params.game_pk));
    if (params.status != null) p = p.set('status', params.status);
    return this.http.get<BetOut[]>(`${this.base}`, { ...this.opts(), params: p });
  }

  createBet(body: {
    bank_id: number;
    game_pk: number;
    bet_type: 'moneyline' | 'over_under';
    bet_side: 'home' | 'away' | 'over' | 'under';
    stake: number;
    odds: number;
    ou_line?: number | null;
    notes?: string | null;
  }): Observable<BetOut> {
    return this.http.post<BetOut>(`${this.base}`, body, this.opts());
  }

  globalStats(bankId?: number): Observable<BetsStatsOut> {
    let p = new HttpParams();
    if (bankId != null) p = p.set('bank_id', String(bankId));
    return this.http.get<BetsStatsOut>(`${this.base}/stats`, { ...this.opts(), params: p });
  }

  resolveBet(betId: number): Observable<BetOut> {
    return this.http.post<BetOut>(`${this.base}/${betId}/resolve`, {}, this.opts());
  }
}
