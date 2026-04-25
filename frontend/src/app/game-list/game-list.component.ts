import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

/** Asegura `YYYY-MM-DD` para comparar con las fechas pedidas (API puede mandar sufijo de tiempo). */
function isoDateOnly(raw: string | undefined | null): string {
  if (raw == null || raw === '') {
    return '';
  }
  return raw.slice(0, 10);
}

import {
  DateChipSelectorComponent,
  type DateChipPreset,
  type DateChipSelection,
} from '../components/date-chip-selector/date-chip-selector.component';
import { FriendlyErrorBannerComponent } from '../components/friendly-error-banner/friendly-error-banner.component';
import { MatchCardComponent } from '../components/match-card/match-card.component';
import type { GameDetail, GamesListMeta } from '../models/game';
import { GamesApiService } from '../services/games-api.service';
import { currentSeasonDateBounds } from '../utils/date-bounds';

@Component({
  selector: 'app-game-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
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

  // Signals para reactividad optimizada (como useMemo + useState)
  games = signal<GameDetail[]>([]);
  homeWinByPk = signal<Record<number, number | null>>({});
  loading = signal(false);
  predictionsLoading = signal(false);
  loadError = signal(false);
  dateSummary = signal('');
  pageTitle = signal('Hoy en MLB');
  pageLede = signal('Partidos del día con estimación de victoria del equipo local.');

  /** Avisos del API (p. ej. snapshots faltantes) sin mirar logs del servidor. */
  listMeta = signal<GamesListMeta | null>(null);

  // Computed: Se recalcula SOLO cuando games() cambia (como useMemo)
  dayKeys = computed(() => {
    const s = new Set(this.games().map((g) => g.game_date));
    return [...s].sort();
  });

  // Computed: Mapa optimizado de juegos por fecha
  gamesByDate = computed(() => {
    const map = new Map<string, GameDetail[]>();
    for (const game of this.games()) {
      const date = game.game_date;
      if (!map.has(date)) {
        map.set(date, []);
      }
      map.get(date)!.push(game);
    }
    return map;
  });

  private lastSelection: string[] = [];

  /**
   * Evita condición de carrera entre peticiones HTTP (p. ej. cambiar chip rápido).
   * Los `computed`/signals solo memorizan derivados en memoria; no sustituyen este control.
   */
  private loadGeneration = 0;

  ngOnInit(): void {
    /* La carga inicial la dispara DateChipSelector al emitir en ngOnInit. */
  }

  onDateSelection(sel: DateChipSelection): void {
    this.dateSummary.set(this.formatDateSummary(sel));
    this.applyHeadlines(sel.preset);
    this.loadForDates(sel.dates);
  }

  private applyHeadlines(preset: DateChipPreset): void {
    if (preset === 'week') {
      this.pageTitle.set('Esta semana en MLB');
      this.pageLede.set(
        'Semana calendario (lunes a domingo) con partidos pasados y próximos. Estimación de victoria del equipo local.'
      );
      return;
    }
    if (preset === 'tomorrow') {
      this.pageTitle.set('Mañana en MLB');
      this.pageLede.set('Partidos del día siguiente con estimación de victoria del equipo local.');
      return;
    }
    this.pageTitle.set('Hoy en MLB');
    this.pageLede.set('Partidos del día con estimación de victoria del equipo local.');
  }

  retry(): void {
    this.loadError.set(false);
    const sel = this.lastSelection;
    if (sel.length > 0) {
      this.loadForDates(sel);
    }
  }

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
      this.games.set([]);
      this.homeWinByPk.set({});
      this.listMeta.set(null);
      return;
    }
    const gen = ++this.loadGeneration;
    this.loading.set(true);
    this.loadError.set(false);
    /** Sin vaciar la lista, `loading && games.length===0` nunca se cumple y siguen viéndose partidos viejos. */
    this.games.set([]);
    this.homeWinByPk.set({});

    const allowed = new Set(dates);
    const emptyMeta = (): GamesListMeta => ({
      warnings: [],
      info: [],
      missing_snapshot_count: 0,
    });
    const reqs = dates.map((d) =>
      this.api.listGames(d, true).pipe(
        catchError(() => of({ games: [], meta: emptyMeta() })),
      ),
    );
    forkJoin(reqs).subscribe({
      next: (chunks) => {
        if (gen !== this.loadGeneration) {
          return;
        }
        const flat = chunks
          .flatMap((c) => c.games)
          .filter((g) => allowed.has(isoDateOnly(g.game_date)));
        const merged = this.mergeGames(flat);
        const warnings = [...new Set(chunks.flatMap((c) => c.meta.warnings))];
        const info = [...new Set(chunks.flatMap((c) => c.meta.info))];
        const missingTotal = chunks.reduce((acc, c) => acc + c.meta.missing_snapshot_count, 0);
        this.listMeta.set({ warnings, info, missing_snapshot_count: missingTotal });
        this.games.set(merged);
        this.loading.set(false);
        if (merged.length > 0 && !('prediction' in merged[0])) {
          this.loadPredictions(merged, gen);
        } else {
          this.applyPredictionsFromPayload(merged);
          this.predictionsLoading.set(false);
        }
      },
      error: () => {
        if (gen !== this.loadGeneration) {
          return;
        }
        this.loading.set(false);
        this.loadError.set(true);
        this.games.set([]);
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

  private applyPredictionsFromPayload(games: GameDetail[]): void {
    const map: Record<number, number | null> = {};
    for (const g of games) {
      const p = g.prediction;
      if (p != null && typeof p.home_win_probability === 'number') {
        map[g.game_pk] = p.home_win_probability;
      } else {
        map[g.game_pk] = null;
      }
    }
    this.homeWinByPk.set(map);
  }

  /** API antiguo sin ``prediction`` en el JSON: una petición /predict por partido. */
  private loadPredictions(games: GameDetail[], gen: number): void {
    if (games.length === 0) {
      return;
    }
    this.predictionsLoading.set(true);
    forkJoin(
      games.map((g) =>
        this.api.predict(g.game_pk).pipe(catchError(() => of(null))),
      ),
    ).subscribe({
      next: (preds) => {
        if (gen !== this.loadGeneration) {
          return;
        }
        const map: Record<number, number | null> = {};
        preds.forEach((p, i) => {
          const pk = games[i].game_pk;
          map[pk] = p ? p.home_win_probability : null;
        });
        this.homeWinByPk.set(map);
        this.predictionsLoading.set(false);
      },
      error: () => {
        if (gen !== this.loadGeneration) {
          return;
        }
        this.predictionsLoading.set(false);
      },
    });
  }

  // Método optimizado: usa el mapa computado en lugar de filtrar cada vez
  gamesForDate(iso: string): GameDetail[] {
    return this.gamesByDate().get(iso) || [];
  }

  probFor(g: GameDetail): number | null | undefined {
    const v = this.homeWinByPk()[g.game_pk];
    if (this.predictionsLoading() && v === undefined) {
      return undefined;
    }
    return v ?? null;
  }
}
