import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { debounceTime, defer, filter, forkJoin, map, merge, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { environment } from '../../environments/environment';

/** Asegura `YYYY-MM-DD` para comparar con las fechas pedidas (API puede mandar sufijo de tiempo). */
function isoDateOnly(raw: string | undefined | null): string {
  if (raw == null || raw === '') {
    return '';
  }
  return raw.slice(0, 10);
}

import {
  buildDateSelectionForPreset,
  DateChipSelectorComponent,
  type DateChipPreset,
  type DateChipSelection,
} from '../components/date-chip-selector/date-chip-selector.component';
import { FriendlyErrorBannerComponent } from '../components/friendly-error-banner/friendly-error-banner.component';
import { MatchCardComponent } from '../components/match-card/match-card.component';
import type { GameDetail, GamesListMeta } from '../models/game';
import { GamesApiService } from '../services/games-api.service';
import { currentSeasonDateBounds } from '../utils/date-bounds';

/** Entrada de caché por rango de fechas (evita GET repetidos al volver a Hoy/Mañana/Semana). */
interface GamesListCacheEntry {
  games: GameDetail[];
  listMeta: GamesListMeta | null;
  homeWinByPk: Record<number, number | null>;
}

function cacheKeyForDates(dates: string[]): string {
  return dates.slice().sort().join('|');
}

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
    MatTooltipModule,
    DateChipSelectorComponent,
    MatchCardComponent,
    FriendlyErrorBannerComponent,
  ],
  templateUrl: './game-list.component.html',
  styleUrl: './game-list.component.scss',
})
export class GameListComponent {
  private readonly api = inject(GamesApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly seasonBounds = currentSeasonDateBounds();

  /** Ruta fija (today|tomorrow|week): no mostrar chips duplicados. */
  hideDateChips = false;

  // Signals para reactividad optimizada (como useMemo + useState)
  games = signal<GameDetail[]>([]);
  homeWinByPk = signal<Record<number, number | null>>({});
  loading = signal(false);
  predictionsLoading = signal(false);
  loadError = signal(false);
  dateSummary = signal('');
  pageTitle = signal('Hoy en MLB');
  pageLede = signal(
    'Partidos del día con favorito del modelo (más % de victoria) y total de carreras (O/U).',
  );

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

  /** useMemo a nivel de petición: mismas fechas = restaurar sin HTTP. `retry` usa `force`. */
  private readonly listCache = new Map<string, GamesListCacheEntry>();

  /**
   * Evita condición de carrera entre peticiones HTTP (p. ej. cambiar chip rápido).
   * Los `computed`/signals solo memorizan derivados en memoria; no sustituyen este control.
   */
  private loadGeneration = 0;

  constructor() {
    // `defer` = URL tras bootstrap; luego cada `NavigationEnd` (cambio real de ruta hija /mlb/...).
    // `debounceTime(0)` agrupa defer + primer NavigationEnd en el mismo turno; no uses `distinctUntilChanged`
    // solo por URL, o si el primer tick lee `datePreset` null aún, el segundo tick no se pierde.
    merge(
      defer(() => of(this.router.url)),
      this.router.events.pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        map((e) => e.urlAfterRedirects),
      ),
    )
      .pipe(debounceTime(0), takeUntilDestroyed())
      .subscribe(() => this.applyDatePresetFromRouter());
  }

  /**
   * En rutas hermanas (`/mlb/today` → `/mlb/tomorrow`) Angular puede reutilizar el mismo
   * `GameListComponent` y el `snapshot.data` del `ActivatedRoute` inyectado a veces **no** se actualiza
   * a tiempo → `datePreset` se queda en `today` y «Mañana» pedía el mismo `date=` que Hoy.
   * La **URL** del `Router` es la fuente de verdad; `data` queda de respaldo.
   */
  private readDatePresetFromTree(): DateChipPreset | null {
    const fromUrl = this.presetFromRouterUrl();
    if (fromUrl != null) {
      return fromUrl;
    }
    const own = this.route.snapshot.data['datePreset'];
    if (typeof own === 'string' && own !== '') {
      return own as DateChipPreset;
    }
    let r: ActivatedRoute | null = this.router.routerState.root;
    let last: DateChipPreset | null = null;
    while (r) {
      const p = r.snapshot.data['datePreset'];
      if (typeof p === 'string' && p !== '') {
        last = p as DateChipPreset;
      }
      r = r.firstChild;
    }
    return last;
  }

  /** Deriva `today|tomorrow|week` del path activo, p. ej. `/mlb/tomorrow` */
  private presetFromRouterUrl(): DateChipPreset | null {
    const path = (this.router.url || '').split('?')[0].split('#')[0];
    const m = /\/mlb\/(today|tomorrow|week)(?:\/|$)/i.exec(path);
    if (m?.[1]) {
      return m[1].toLowerCase() as DateChipPreset;
    }
    return null;
  }

  private applyDatePresetFromRouter(): void {
    const preset = this.readDatePresetFromTree();
    if (preset == null) {
      return;
    }
    this.hideDateChips = true;
    const b = this.seasonBounds;
    const sel = buildDateSelectionForPreset(preset, b.min, b.max);
    // Navegación intencional (Hoy/Mañana/Semana): la URL ya cambió; no bloquear con clave de fechas.
    // Si el usuario vuelve al mismo preset más tarde, `loadForDates` puede usar caché por `cacheKey` si aplica.
    this.onDateSelection(sel);
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
        'Semana calendario (lunes a domingo) con partidos pasados y próximos. Favorito del modelo y total de carreras (O/U).',
      );
      return;
    }
    if (preset === 'tomorrow') {
      this.pageTitle.set('Mañana en MLB');
      this.pageLede.set(
        'Partidos del día siguiente con favorito del modelo y total de carreras (O/U).',
      );
      return;
    }
    this.pageTitle.set('Hoy en MLB');
    this.pageLede.set(
      'Partidos del día con favorito del modelo (más % de victoria) y total de carreras (O/U).',
    );
  }

  retry(): void {
    this.loadError.set(false);
    const sel = this.lastSelection;
    if (sel.length > 0) {
      this.loadForDates(sel, { force: true });
    }
  }

  /**
   * Acción explícita del botón «Actualizar»: ignora cachés (componente y servicio)
   * y vuelve a pedir al backend. Útil si el usuario sabe que hubo una nueva sincronización
   * o predicción y la respuesta cacheada en cliente quedó desfasada antes del TTL.
   */
  forceReload(): void {
    this.retry();
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

  private loadForDates(dates: string[], options?: { force?: boolean }): void {
    const force = options?.force === true;
    this.lastSelection = dates;
    if (dates.length === 0) {
      this.games.set([]);
      this.homeWinByPk.set({});
      this.listMeta.set(null);
      return;
    }
    const cacheKey = cacheKeyForDates(dates);
    if (!force) {
      const hit = this.listCache.get(cacheKey);
      if (hit != null) {
        if (!environment.production) {
          console.log(
            '[GameList] cache hit — sin HTTP; clave:',
            cacheKey,
            '(usa force/reintento o cambia rango para volver a pedir al API)',
          );
        }
        this.listMeta.set(hit.listMeta);
        this.games.set(hit.games);
        this.homeWinByPk.set(hit.homeWinByPk);
        this.loading.set(false);
        this.loadError.set(false);
        this.predictionsLoading.set(false);
        return;
      }
    } else {
      this.listCache.delete(cacheKey);
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
      this.api.listGames(d, true, { force }).pipe(
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
          this.loadPredictions(merged, gen, cacheKey, force);
        } else {
          this.applyPredictionsFromPayload(merged);
          this.predictionsLoading.set(false);
          this.putListCache(
            cacheKey,
            merged,
            { warnings, info, missing_snapshot_count: missingTotal },
            this.homeWinByPk(),
          );
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

  private putListCache(
    key: string,
    games: GameDetail[],
    meta: GamesListMeta,
    homeWin: Record<number, number | null>,
  ): void {
    this.listCache.set(key, {
      games,
      listMeta: meta,
      homeWinByPk: { ...homeWin },
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
  private loadPredictions(
    games: GameDetail[],
    gen: number,
    cacheKey: string,
    force = false,
  ): void {
    if (games.length === 0) {
      return;
    }
    this.predictionsLoading.set(true);
    forkJoin(
      games.map((g) =>
        this.api.predict(g.game_pk, { force }).pipe(catchError(() => of(null))),
      ),
    ).subscribe({
      next: (preds) => {
        if (gen !== this.loadGeneration) {
          return;
        }
        const map: Record<number, number | null> = {};
        preds.forEach((p, i) => {
          const pk = games[i]!.game_pk;
          map[pk] = p ? p.home_win_probability : null;
        });
        this.homeWinByPk.set(map);
        this.predictionsLoading.set(false);
        const m = this.listMeta();
        this.putListCache(
          cacheKey,
          this.games(),
          m ?? { warnings: [], info: [], missing_snapshot_count: 0 },
          map,
        );
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
