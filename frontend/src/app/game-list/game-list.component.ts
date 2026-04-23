import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { DateChipSelectorComponent, type DateChipSelection } from '../components/date-chip-selector/date-chip-selector.component';
import { FriendlyErrorBannerComponent } from '../components/friendly-error-banner/friendly-error-banner.component';
import { MatchCardComponent } from '../components/match-card/match-card.component';
import type { GameDetail } from '../models/game';
import { GamesApiService } from '../services/games-api.service';
import { currentSeasonDateBounds } from '../utils/date-bounds';

@Component({
  selector: 'app-game-list',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    DateChipSelectorComponent,
    MatchCardComponent,
    FriendlyErrorBannerComponent,
  ],
  templateUrl: './game-list.component.html',
  styleUrl: './game-list.component.scss',
})
export class GameListComponent implements OnInit {
  private readonly api = inject(GamesApiService);

  readonly seasonBounds = currentSeasonDateBounds();

  games: GameDetail[] = [];
  /** Fechas únicas ordenadas (evita recomputar en plantilla). */
  dayKeys: string[] = [];
  /** Probabilidad victoria local por partido (fracción 0–1). */
  homeWinByPk: Record<number, number | null> = {};
  loading = false;
  predictionsLoading = false;
  loadError = false;

  /** Preset de fechas actual (para subtítulos). */
  dateSummary = '';

  ngOnInit(): void {
    /* La carga inicial la dispara DateChipSelector al emitir en ngOnInit. */
  }

  onDateSelection(sel: DateChipSelection): void {
    this.dateSummary = this.formatDateSummary(sel);
    this.loadForDates(sel.dates);
  }

  retry(): void {
    this.loadError = false;
    const sel = this.lastSelection;
    if (sel.length > 0) {
      this.loadForDates(sel);
    }
  }

  private lastSelection: string[] = [];

  private formatDateSummary(sel: DateChipSelection): string {
    if (sel.dates.length === 0) {
      return '';
    }
    if (sel.preset === 'week') {
      return `${sel.dates[0]} — ${sel.dates[sel.dates.length - 1]}`;
    }
    return sel.dates[0];
  }

  private loadForDates(dates: string[]): void {
    this.lastSelection = dates;
    if (dates.length === 0) {
      this.games = [];
      this.dayKeys = [];
      this.homeWinByPk = {};
      return;
    }
    this.loading = true;
    this.loadError = false;
    this.homeWinByPk = {};

    const reqs = dates.map((d) => this.api.listGames(d, true));
    forkJoin(reqs).subscribe({
      next: (chunks) => {
        const merged = this.mergeGames(chunks.flat());
        this.games = merged;
        this.dayKeys = this.computeDayKeys(merged);
        this.loading = false;
        this.loadPredictions(merged);
      },
      error: () => {
        this.loading = false;
        this.loadError = true;
        this.games = [];
        this.dayKeys = [];
      },
    });
  }

  private mergeGames(rows: GameDetail[]): GameDetail[] {
    const byPk = new Map<number, GameDetail>();
    for (const g of rows) {
      if (!byPk.has(g.game_pk)) {
        byPk.set(g.game_pk, g);
      }
    }
    return [...byPk.values()].sort((a, b) => {
      if (a.game_date !== b.game_date) {
        return a.game_date.localeCompare(b.game_date);
      }
      return a.game_pk - b.game_pk;
    });
  }

  private loadPredictions(games: GameDetail[]): void {
    if (games.length === 0) {
      return;
    }
    this.predictionsLoading = true;
    forkJoin(
      games.map((g) =>
        this.api.predict(g.game_pk).pipe(catchError(() => of(null))),
      ),
    ).subscribe({
      next: (preds) => {
        const map: Record<number, number | null> = {};
        preds.forEach((p, i) => {
          const pk = games[i].game_pk;
          map[pk] = p ? p.home_win_probability : null;
        });
        this.homeWinByPk = map;
        this.predictionsLoading = false;
      },
      error: () => {
        this.predictionsLoading = false;
      },
    });
  }

  gamesForDate(iso: string): GameDetail[] {
    return this.games.filter((g) => g.game_date === iso);
  }

  private computeDayKeys(games: GameDetail[]): string[] {
    const s = new Set(games.map((g) => g.game_date));
    return [...s].sort();
  }

  probFor(g: GameDetail): number | null | undefined {
    const v = this.homeWinByPk[g.game_pk];
    if (this.predictionsLoading && v === undefined) {
      return undefined;
    }
    return v ?? null;
  }
}
