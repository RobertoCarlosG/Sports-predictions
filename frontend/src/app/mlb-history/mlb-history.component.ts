import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';

import type { TeamOut } from '../models/game';
import type { HistoryGame } from '../models/history';
import { GamesApiService } from '../services/games-api.service';
import { mlbDisplayAbbrev } from '../utils/mlb-team-abbr';
import { currentSeasonDateBounds, eachIsoDateInRange } from '../utils/date-bounds';
import { parseApiError, type ApiErrorView } from '../utils/api-error';

@Component({
  selector: 'app-mlb-history',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatDividerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatListModule,
    MatProgressSpinnerModule,
    MatSelectModule,
  ],
  templateUrl: './mlb-history.component.html',
  styleUrl: './mlb-history.component.scss',
})
export class MlbHistoryComponent implements OnInit {
  private readonly api = inject(GamesApiService);

  season = String(new Date().getFullYear());
  /** Vacío = todos los equipos */
  teamId: string | number = '';
  dateFrom = '';
  dateTo = '';
  onlyFinal = true;
  onlyWithScores = false;
  limit = 150;

  teams: TeamOut[] = [];
  games: HistoryGame[] = [];
  loading = false;
  errorView: ApiErrorView | null = null;

  syncStart = '';
  syncEnd = '';
  syncFetchDetails = false;
  syncLoading = false;
  syncMessage: string | null = null;

  /** min/max para inputs type=date (año en curso, fin ≤ hoy). */
  readonly seasonBounds = currentSeasonDateBounds();

  ngOnInit(): void {
    const { year: y, min, max } = this.seasonBounds;
    this.season = String(y);
    this.syncStart = `${y}-03-01`;
    this.syncEnd = max;
    this.dateFrom = min;
    this.dateTo = max;
    this.api.listMlbTeams().subscribe({
      next: (t) => {
        this.teams = t;
      },
      error: () => {
        this.teams = [];
      },
    });
    void this.load();
  }

  load(): void {
    this.loading = true;
    this.errorView = null;
    this.api
      .listMlbHistory({
        season: this.season.trim() || undefined,
        team_id: this.teamId === '' ? undefined : Number(this.teamId),
        from: this.dateFrom || undefined,
        to: this.dateTo || undefined,
        only_final: this.onlyFinal,
        only_with_scores: this.onlyWithScores,
        limit: this.limit,
        offset: 0,
      })
      .subscribe({
        next: (g) => {
          this.games = g;
          this.loading = false;
        },
        error: (e: unknown) => {
          this.loading = false;
          this.errorView = parseApiError(e);
        },
      });
  }

  runSyncRange(): void {
    if (!this.syncStart || !this.syncEnd) {
      this.syncMessage = 'Indica inicio y fin del rango.';
      return;
    }
    const { min, max } = this.seasonBounds;
    if (this.syncStart < min || this.syncEnd > max || this.syncStart > this.syncEnd) {
      this.syncMessage = `Usa solo fechas del ${min} al ${max} (año en curso, sin futuro).`;
      return;
    }
    const days = eachIsoDateInRange(this.syncStart, this.syncEnd);
    if (days.length === 0) {
      this.syncMessage = 'Rango de fechas vacío.';
      return;
    }
    this.syncLoading = true;
    this.syncMessage = null;
    const fetchDetails = this.syncFetchDetails;
    const runDay = (i: number): void => {
      if (i >= days.length) {
        this.syncLoading = false;
        this.syncMessage = `Listo: ${days.length} día(s) sincronizado(s).`;
        void this.load();
        return;
      }
      const d = days[i];
      this.syncMessage = `Sincronizando ${d} (${i + 1}/${days.length})…`;
      this.api
        .syncMlbRange({
          start_date: d,
          end_date: d,
          fetch_details: fetchDetails,
        })
        .subscribe({
          next: () => runDay(i + 1),
          error: (e: unknown) => {
            this.syncLoading = false;
            this.syncMessage = parseApiError(e).summary;
          },
        });
    };
    runDay(0);
  }

  scoreLine(g: HistoryGame): string {
    if (typeof g.away_score === 'number' && typeof g.home_score === 'number') {
      return `${g.away_score} – ${g.home_score}`;
    }
    return '—';
  }

  abbr(team: TeamOut): string {
    return mlbDisplayAbbrev(team);
  }
}
