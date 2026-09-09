import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { forkJoin, of } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';

import { BoxscoreViewComponent } from '../boxscore-view/boxscore-view.component';
import { CollapsibleSectionComponent } from '../components/collapsible-section/collapsible-section.component';
import { FriendlyErrorBannerComponent } from '../components/friendly-error-banner/friendly-error-banner.component';
import { ProbabilityBarComponent } from '../components/probability-bar/probability-bar.component';
import { StatusBadgeComponent } from '../components/status-badge/status-badge.component';
import { WeatherChipComponent } from '../components/weather-chip/weather-chip.component';
import type { GameDetail, PredictionOut, TeamOut } from '../models/game';
import type { HistoryGame } from '../models/history';
import { GamesApiService } from '../services/games-api.service';
import { mlbDisplayAbbrev } from '../utils/mlb-team-abbr';
import { favoriteFromHomeWinProbability } from '../utils/prediction-favorite';

@Component({
  selector: 'app-game-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatButtonToggleModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    BoxscoreViewComponent,
    CollapsibleSectionComponent,
    FriendlyErrorBannerComponent,
    ProbabilityBarComponent,
    StatusBadgeComponent,
    WeatherChipComponent,
  ],
  templateUrl: './game-detail.component.html',
  styleUrl: './game-detail.component.scss',
})
export class GameDetailComponent implements OnInit {
  private readonly api = inject(GamesApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly cdr = inject(ChangeDetectorRef);

  headToHead: HistoryGame[] = [];

  loading = false;
  predLoading = false;
  xgbLoading = false;
  xgbUnavailable = false;
  refreshLoading = false;
  predictionRefreshLoading = false;
  loadError = false;
  refreshError = false;
  predictionRefreshMessage: string | null = null;
  predictionRefreshIsError = false;

  private readonly selectedModelState = signal<'rf' | 'xgb'>('xgb');
  private readonly rfPredictionState = signal<PredictionOut | null>(null);
  private readonly xgbPredictionState = signal<PredictionOut | null>(null);
  private readonly gameState = signal<GameDetail | null>(null);

  get game(): GameDetail | null {
    return this.gameState();
  }

  set game(value: GameDetail | null) {
    this.gameState.set(value);
  }

  get selectedModel(): 'rf' | 'xgb' {
    return this.selectedModelState();
  }

  set selectedModel(model: 'rf' | 'xgb') {
    this.selectedModelState.set(model);
  }

  get rfPrediction(): PredictionOut | null {
    return this.rfPredictionState();
  }

  set rfPrediction(value: PredictionOut | null) {
    this.rfPredictionState.set(value);
  }

  get xgbPrediction(): PredictionOut | null {
    return this.xgbPredictionState();
  }

  set xgbPrediction(value: PredictionOut | null) {
    this.xgbPredictionState.set(value);
  }

  private gamePk: number | null = null;

  /** Señal: el bloque de estimación anidado tiene que leerla o no se refresca al cambiar de modelo. */
  readonly activePrediction = computed(() =>
    this.selectedModelState() === 'xgb' ? this.xgbPredictionState() : this.rfPredictionState(),
  );

  /**
   * Una fila con clave de modelo: `@for` destruye el DOM al cambiar de algoritmo
   * (si no, el texto puede quedarse pegado — p. ej. con el traductor del navegador).
   */
  readonly modelViews = computed(() => {
    const model = this.selectedModelState();
    const pred = this.activePrediction();
    return [
      {
        key: `${model}:${pred?.model_version ?? 'empty'}`,
        model,
        pred,
      },
    ];
  });

  /** true = la predicción activa usó constantes por falta de datos; la prob. ~50% no es fiable. */
  readonly insufficientData = computed(() => this.activePrediction()?.defaults_injected === true);

  ngOnInit(): void {
    this.route.paramMap.subscribe((pm) => {
      const pk = pm.get('gamePk');
      if (!pk) {
        this.loadError = true;
        return;
      }
      this.gamePk = Number(pk);
      void this.loadGame(this.gamePk);
    });
  }

  retryLoad(): void {
    if (this.gamePk == null) {
      return;
    }
    void this.loadGame(this.gamePk, { force: true });
  }

  private loadGame(gamePk: number, options?: { force?: boolean }): void {
    const force = options?.force === true;
    this.loading = true;
    this.loadError = false;
    this.refreshError = false;
    this.predictionRefreshMessage = null;
    this.predictionRefreshIsError = false;
    this.rfPrediction = null;
    this.xgbPrediction = null;
    this.xgbUnavailable = false;
    this.headToHead = [];
    this.api.getGame(gamePk, { force }).subscribe({
      next: (g) => {
        this.game = g;
        this.loading = false;
        if (g.prediction != null) {
          this.storePrediction(g.prediction);
        }
        if (this.xgbPrediction == null) {
          this.loadXgbPrediction(gamePk, { force });
        } else {
          this.xgbLoading = false;
        }
        if (this.rfPrediction == null) {
          this.loadRfPrediction(gamePk, { force });
        }
        this.loadHeadToHead(g);
      },
      error: () => {
        this.loading = false;
        this.loadError = true;
        this.game = null;
      },
    });
  }

  private loadRfPrediction(gamePk: number, options?: { force?: boolean }): void {
    this.predLoading = true;
    this.api.predict(gamePk, { force: options?.force === true, model: 'rf' }).subscribe({
      next: (p) => {
        this.storePrediction(p, 'rf');
        this.predLoading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.rfPrediction = null;
        this.predLoading = false;
        this.cdr.markForCheck();
      },
    });
  }

  private loadXgbPrediction(gamePk: number, options?: { force?: boolean }): void {
    this.xgbLoading = true;
    this.xgbUnavailable = false;
    this.api.predict(gamePk, { force: options?.force === true, model: 'xgb' }).subscribe({
      next: (p) => {
        this.storePrediction(p, 'xgb');
        this.xgbLoading = false;
        this.cdr.markForCheck();
      },
      error: (err: { status?: number }) => {
        this.xgbPrediction = null;
        this.xgbLoading = false;
        if (err?.status === 503) {
          this.xgbUnavailable = true;
        }
        this.cdr.markForCheck();
      },
    });
  }

  /** Guarda RF/XGB según `model_version`, no según quién hizo la petición. */
  private storePrediction(p: PredictionOut, fallback: 'rf' | 'xgb' = 'xgb'): void {
    const v = (p.model_version ?? '').toLowerCase();
    if (v.includes('xgb')) {
      this.xgbPrediction = p;
      return;
    }
    if (v.includes('rf') || v.includes('forest') || v.includes('synthetic')) {
      this.rfPrediction = p;
      return;
    }
    if (fallback === 'rf') {
      this.rfPrediction = p;
    } else {
      this.xgbPrediction = p;
    }
  }

  private loadHeadToHead(g: GameDetail): void {
    const homeId = g.home_team.id;
    const awayId = g.away_team.id;
    this.api
      .listMlbHistory({
        team_id: homeId,
        only_final: true,
        only_with_scores: true,
        limit: 150,
      })
      .pipe(catchError(() => of([] as HistoryGame[])))
      .subscribe((rows) => {
        this.headToHead = rows
          .filter(
            (r) =>
              r.game_pk !== g.game_pk &&
              ((r.home_team.id === homeId && r.away_team.id === awayId) ||
                (r.home_team.id === awayId && r.away_team.id === homeId)),
          )
          .slice(0, 12);
      });
  }

  hasScore(g: GameDetail): boolean {
    return typeof g.away_score === 'number' && typeof g.home_score === 'number';
  }

  abbr(t: TeamOut): string {
    return mlbDisplayAbbrev(t);
  }

  selectModel(model: 'rf' | 'xgb'): void {
    if (model !== 'rf' && model !== 'xgb') {
      return;
    }
    this.selectedModelState.set(model);
    this.cdr.detectChanges();
  }

  /** Un solo control: actualiza calendario, condiciones y estimación. */
  refreshData(): void {
    if (!this.game) {
      return;
    }
    const pk = this.game.game_pk;
    this.refreshLoading = true;
    this.refreshError = false;
    this.predictionRefreshMessage = null;
    this.predictionRefreshIsError = false;
    this.api
      .syncMlbGame(pk, true)
      .pipe(
        switchMap((g) => {
          this.game = g;
          return this.api.refreshWeather(pk).pipe(catchError(() => of(this.game!)));
        }),
        switchMap((g) => {
          this.game = g;
          return forkJoin({
            detail: this.api.getGame(pk, { force: true }).pipe(catchError(() => of(g))),
            rfPred: this.api.predict(pk, { force: true, model: 'rf' }).pipe(catchError(() => of(null))),
            xgbPred: this.api.predict(pk, { force: true, model: 'xgb' }).pipe(catchError(() => of(null))),
          });
        }),
      )
      .subscribe({
        next: ({ detail, rfPred, xgbPred }) => {
          this.game = detail;
          if (rfPred) {
            this.storePrediction(rfPred, 'rf');
          } else {
            this.rfPrediction = null;
          }
          if (xgbPred) {
            this.storePrediction(xgbPred, 'xgb');
          } else {
            this.xgbPrediction = null;
          }
          this.refreshLoading = false;
          if (this.game) {
            this.loadHeadToHead(this.game);
          }
        },
        error: () => {
          this.refreshLoading = false;
          this.refreshError = true;
        },
      });
  }

  /**
   * Probabilidad del **favorito** (lado con mayor P de victoria) para la barra única.
   */
  readonly favoriteBarProbability = computed(() => {
    const p = this.activePrediction()?.home_win_probability;
    if (p == null || Number.isNaN(p)) {
      return null;
    }
    return favoriteFromHomeWinProbability(p).favoriteWinProb;
  });

  readonly favoriteVictoryLabel = computed(() => {
    const g = this.gameState();
    if (g == null) {
      return 'Victoria del favorito';
    }
    const { favorite, favoriteWinProb } = favoriteFromHomeWinProbability(
      this.activePrediction()?.home_win_probability,
    );
    if (favorite === 'none' || favoriteWinProb == null) {
      return 'Victoria del favorito';
    }
    const team = favorite === 'home' ? g.home_team : g.away_team;
    return `Victoria ${this.abbr(team)}`;
  });

  readonly hasRunsProjection = computed(() => {
    const p = this.activePrediction();
    return (
      p != null &&
      typeof p.total_runs_estimate === 'number' &&
      Number.isFinite(p.total_runs_estimate) &&
      typeof p.over_under_line === 'number' &&
      Number.isFinite(p.over_under_line)
    );
  });

  readonly runsEstimateFormatted = computed(() => {
    const p = this.activePrediction();
    if (p == null || !this.hasRunsProjection()) {
      return '';
    }
    return this.formatRunNumber(p.total_runs_estimate);
  });

  readonly ouLineFormatted = computed(() => {
    const p = this.activePrediction();
    if (p == null || !this.hasRunsProjection()) {
      return '';
    }
    return this.formatRunNumber(p.over_under_line);
  });

  readonly runsLeanLabel = computed(() => {
    switch (this.runsLeanKind()) {
      case 'over':
        return 'Sobre';
      case 'under':
        return 'Bajo';
      default:
        return 'En la línea';
    }
  });

  readonly runsLeanClass = computed(() => {
    const k = this.runsLeanKind();
    return {
      'detail-lean-over': k === 'over',
      'detail-lean-under': k === 'under',
      'detail-lean-push': k === 'push',
    };
  });

  readonly ahHomeLabel = computed(() => this.ahSideLabel(this.activePrediction()?.asian_handicap?.home));

  readonly ahAwayLabel = computed(() => this.ahSideLabel(this.activePrediction()?.asian_handicap?.away));

  private runsLeanKind(): 'over' | 'under' | 'push' {
    const p = this.activePrediction();
    if (p == null || !this.hasRunsProjection()) {
      return 'push';
    }
    const d = p.total_runs_estimate - p.over_under_line;
    if (d > 0.02) {
      return 'over';
    }
    if (d < -0.02) {
      return 'under';
    }
    return 'push';
  }

  private formatRunNumber(n: number): string {
    return n.toFixed(1).replace('.', ',');
  }

  formatRuns(n: number): string {
    return this.formatRunNumber(n);
  }

  favoriteProb(p: PredictionOut): number | null {
    const ph = p.home_win_probability;
    if (ph == null || Number.isNaN(ph)) {
      return null;
    }
    return favoriteFromHomeWinProbability(ph).favoriteWinProb;
  }

  favoriteLabel(p: PredictionOut): string {
    const g = this.gameState();
    if (g == null) {
      return 'Victoria del favorito';
    }
    const { favorite, favoriteWinProb } = favoriteFromHomeWinProbability(p.home_win_probability);
    if (favorite === 'none' || favoriteWinProb == null) {
      return 'Victoria del favorito';
    }
    const team = favorite === 'home' ? g.home_team : g.away_team;
    return `Victoria ${this.abbr(team)}`;
  }

  predHasRuns(p: PredictionOut): boolean {
    return (
      typeof p.total_runs_estimate === 'number' &&
      Number.isFinite(p.total_runs_estimate) &&
      typeof p.over_under_line === 'number' &&
      Number.isFinite(p.over_under_line)
    );
  }

  predLeanLabel(p: PredictionOut): string {
    switch (this.predLeanKind(p)) {
      case 'over':
        return 'Sobre';
      case 'under':
        return 'Bajo';
      default:
        return 'En la línea';
    }
  }

  predLeanClass(p: PredictionOut): Record<string, boolean> {
    const k = this.predLeanKind(p);
    return {
      'detail-lean-over': k === 'over',
      'detail-lean-under': k === 'under',
      'detail-lean-push': k === 'push',
    };
  }

  ahLabel(side: { team_abbr: string; line: number }): string {
    return this.ahSideLabel(side);
  }

  private predLeanKind(p: PredictionOut): 'over' | 'under' | 'push' {
    if (!this.predHasRuns(p)) {
      return 'push';
    }
    const d = p.total_runs_estimate - p.over_under_line;
    if (d > 0.02) {
      return 'over';
    }
    if (d < -0.02) {
      return 'under';
    }
    return 'push';
  }

  private ahSideLabel(side: { team_abbr: string; line: number } | null | undefined): string {
    if (!side) {
      return '';
    }
    return `${side.team_abbr} ${this.formatSignedLine(side.line)}`;
  }

  private formatSignedLine(v: number): string {
    if (v > 0) {
      return `+${v}`;
    }
    return String(v);
  }

  /** Solo estimación: no descarga calendario ni condiciones. */
  refreshPredictionOnly(): void {
    if (this.gamePk == null) {
      return;
    }
    const requestedGamePk = this.gamePk;
    const requestedModel = this.selectedModel;
    this.predictionRefreshLoading = true;
    this.predictionRefreshMessage = null;
    this.predictionRefreshIsError = false;
    this.api.refreshPrediction(this.gamePk, { model: requestedModel }).subscribe({
      next: (p) => {
        if (this.gamePk !== requestedGamePk) {
          return;
        }
        if (requestedModel === 'xgb') {
          this.xgbPrediction = p;
        } else {
          this.rfPrediction = p;
        }
        this.predictionRefreshLoading = false;
        this.predictionRefreshIsError = false;
        this.predictionRefreshMessage = 'Listo: estimación actualizada.';
      },
      error: () => {
        this.predictionRefreshLoading = false;
        this.predictionRefreshIsError = true;
        this.predictionRefreshMessage =
          'No pudimos actualizar la estimación. Inténtalo otra vez en unos segundos.';
      },
    });
  }
}
