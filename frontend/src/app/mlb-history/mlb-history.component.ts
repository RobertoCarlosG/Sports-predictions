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
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';

import { FilterDrawerComponent } from '../components/filter-drawer/filter-drawer.component';
import { FriendlyErrorBannerComponent } from '../components/friendly-error-banner/friendly-error-banner.component';
import { MatchCardComponent } from '../components/match-card/match-card.component';
import type { TeamOut } from '../models/game';
import type { HistoryGame } from '../models/history';
import { GamesApiService } from '../services/games-api.service';
import { addDaysIso, currentSeasonDateBounds, eachIsoDateInRange } from '../utils/date-bounds';
type QuickRange = 'last7' | 'month' | 'season';

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
    MatProgressSpinnerModule,
    MatSelectModule,
    FilterDrawerComponent,
    MatchCardComponent,
    FriendlyErrorBannerComponent,
  ],
  templateUrl: './mlb-history.component.html',
  styleUrl: './mlb-history.component.scss',
})
export class MlbHistoryComponent implements OnInit {
  private readonly api = inject(GamesApiService);

  season = String(new Date().getFullYear());
  teamId: string | number = '';
  dateFrom = '';
  dateTo = '';
  onlyFinal = true;
  onlyWithScores = false;
  limit = 150;

  teams: TeamOut[] = [];
  games: HistoryGame[] = [];
  loading = false;
  loadError = false;

  syncStart = '';
  syncEnd = '';
  syncExtraDetails = false;
  syncLoading = false;
  syncBanner: string | null = null;

  readonly seasonBounds = currentSeasonDateBounds();
  quickActive: QuickRange = 'last7';

  seasonYearChoices: number[] = [];

  ngOnInit(): void {
    const y = this.seasonBounds.year;
    this.seasonYearChoices = [y - 1, y, y + 1].filter((n) => n >= 2020);
    this.season = String(y);
    this.syncStart = `${y}-03-01`;
    this.syncEnd = this.seasonBounds.max;
    this.applyQuick('last7', false);
    void this.load();
    this.api.listMlbTeams().subscribe({
      next: (t) => {
        this.teams = t;
      },
      error: () => {
        this.teams = [];
      },
    });
  }

  applyQuick(which: QuickRange, reload = true): void {
    this.quickActive = which;
    const max = this.seasonBounds.max;
    const min = this.seasonBounds.min;
    if (which === 'last7') {
      this.dateFrom = addDaysIso(max, -6);
      this.dateTo = max;
    } else if (which === 'month') {
      const parts = max.split('-').map(Number);
      const first = `${parts[0]}-${String(parts[1]).padStart(2, '0')}-01`;
      this.dateFrom = first < min ? min : first;
      this.dateTo = max;
    } else {
      this.dateFrom = min;
      this.dateTo = max;
      this.season = String(this.seasonBounds.year);
    }
    if (reload) {
      void this.load();
    }
  }

  load(): void {
    this.loading = true;
    this.loadError = false;
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
        error: () => {
          this.loading = false;
          this.loadError = true;
        },
      });
  }

  retryLoad(): void {
    this.load();
  }

  runSyncRange(): void {
    if (!this.syncStart || !this.syncEnd) {
      this.syncBanner = 'Elige fechas de inicio y fin.';
      return;
    }
    const { min, max } = this.seasonBounds;
    if (this.syncStart < min || this.syncEnd > max || this.syncStart > this.syncEnd) {
      this.syncBanner = `Usa solo fechas entre ${min} y ${max}.`;
      return;
    }
    const days = eachIsoDateInRange(this.syncStart, this.syncEnd);
    if (days.length === 0) {
      this.syncBanner = 'El rango de fechas no es válido.';
      return;
    }
    this.syncLoading = true;
    this.syncBanner = null;
    const fetchDetails = this.syncExtraDetails;
    const runDay = (i: number): void => {
      if (i >= days.length) {
        this.syncLoading = false;
        this.syncBanner = `Listo: se actualizaron ${days.length} día(s).`;
        void this.load();
        return;
      }
      const d = days[i];
      this.syncBanner = `Procesando ${d} (${i + 1} de ${days.length})…`;
      this.api
        .syncMlbRange({
          start_date: d,
          end_date: d,
          fetch_details: fetchDetails,
        })
        .subscribe({
          next: () => runDay(i + 1),
          error: () => {
            this.syncLoading = false;
            this.syncBanner = 'No pudimos completar la actualización. Inténtalo de nuevo más tarde.';
          },
        });
    };
    runDay(0);
  }

  applyFiltersAndClose(drawer: { close(): void }): void {
    void this.load();
    drawer.close();
  }

  yearStr(y: number): string {
    return String(y);
  }
}
