import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, debounceTime, defer, filter, forkJoin, map, merge, of } from 'rxjs';

import { NbaMatchCardComponent } from '../nba-match-card/nba-match-card.component';
import type { NbaGameDetail } from '../../models/nba';
import { GamesApiService } from '../../services/games-api.service';

type DatePreset = 'today' | 'tomorrow' | 'week';

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function datesForPreset(preset: DatePreset): string[] {
  const base = new Date();
  if (preset === 'today') {
    return [isoDate(base)];
  }
  if (preset === 'tomorrow') {
    const t = new Date(base);
    t.setDate(t.getDate() + 1);
    return [isoDate(t)];
  }
  // week: hoy + 6 días
  const out: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(base);
    d.setDate(d.getDate() + i);
    out.push(isoDate(d));
  }
  return out;
}

@Component({
  selector: 'app-nba-game-list',
  standalone: true,
  imports: [CommonModule, MatIconModule, MatProgressSpinnerModule, NbaMatchCardComponent],
  templateUrl: './nba-game-list.component.html',
  styleUrl: './nba-game-list.component.scss',
})
export class NbaGameListComponent {
  private readonly api = inject(GamesApiService);
  private readonly router = inject(Router);

  readonly skeletonItems = [1, 2, 3, 4, 5, 6];

  games = signal<NbaGameDetail[]>([]);
  homeWinById = signal<Record<string, number | null>>({});
  loading = signal(false);
  loadError = signal(false);
  pageTitle = signal('Hoy en NBA');
  pageLede = signal(
    'Partidos del día con favorito del modelo (XGBoost), spread y puntos totales (O/U).',
  );

  private loadGeneration = 0;

  gamesByDate = computed(() => {
    const m = new Map<string, NbaGameDetail[]>();
    for (const g of this.games()) {
      const k = g.game_date.slice(0, 10);
      (m.get(k) ?? m.set(k, []).get(k)!).push(g);
    }
    return m;
  });

  dayKeys = computed(() => [...this.gamesByDate().keys()].sort());

  constructor() {
    merge(
      defer(() => of(this.router.url)),
      this.router.events.pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        map((e) => e.urlAfterRedirects),
      ),
    )
      .pipe(debounceTime(0), takeUntilDestroyed())
      .subscribe(() => this.applyPreset());
  }

  private presetFromUrl(): DatePreset {
    const path = (this.router.url || '').split('?')[0];
    const m = /\/nba\/(today|tomorrow|week)(?:\/|$)/i.exec(path);
    return (m?.[1]?.toLowerCase() as DatePreset) ?? 'today';
  }

  private applyPreset(): void {
    const preset = this.presetFromUrl();
    if (preset === 'week') {
      this.pageTitle.set('Esta semana en NBA');
    } else if (preset === 'tomorrow') {
      this.pageTitle.set('Mañana en NBA');
    } else {
      this.pageTitle.set('Hoy en NBA');
    }
    this.loadForDates(datesForPreset(preset));
  }

  retry(): void {
    this.loadError.set(false);
    this.loadForDates(datesForPreset(this.presetFromUrl()), true);
  }

  private loadForDates(dates: string[], force = false): void {
    const gen = ++this.loadGeneration;
    this.loading.set(true);
    this.loadError.set(false);
    this.games.set([]);
    this.homeWinById.set({});

    const reqs = dates.map((d) =>
      this.api
        .listNbaGames(d, true, { force })
        .pipe(catchError(() => of({ games: [], meta: { warnings: [], info: [], missing_snapshot_count: 0 } }))),
    );
    forkJoin(reqs).subscribe({
      next: (chunks) => {
        if (gen !== this.loadGeneration) {
          return;
        }
        const flat = chunks.flatMap((c) => c.games);
        const byId = new Map<string, NbaGameDetail>();
        for (const g of flat) {
          if (!byId.has(g.game_id)) {
            byId.set(g.game_id, g);
          }
        }
        const merged = [...byId.values()].sort((a, b) =>
          a.game_date !== b.game_date
            ? a.game_date.localeCompare(b.game_date)
            : a.game_id.localeCompare(b.game_id),
        );
        const probs: Record<string, number | null> = {};
        for (const g of merged) {
          probs[g.game_id] = g.prediction?.home_win_probability ?? null;
        }
        this.games.set(merged);
        this.homeWinById.set(probs);
        this.loading.set(false);
      },
      error: () => {
        if (gen !== this.loadGeneration) {
          return;
        }
        this.loading.set(false);
        this.loadError.set(true);
      },
    });
  }

  gamesForDate(iso: string): NbaGameDetail[] {
    return this.gamesByDate().get(iso) ?? [];
  }

  probFor(g: NbaGameDetail): number | null {
    return this.homeWinById()[g.game_id] ?? null;
  }
}
