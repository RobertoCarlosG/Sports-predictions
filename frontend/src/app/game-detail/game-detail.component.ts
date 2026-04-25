import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
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
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
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

  game: GameDetail | null = null;
  prediction: PredictionOut | null = null;
  headToHead: HistoryGame[] = [];

  loading = false;
  predLoading = false;
  refreshLoading = false;
  predictionRefreshLoading = false;
  loadError = false;
  refreshError = false;
  predictionRefreshMessage: string | null = null;
  predictionRefreshIsError = false;

  private gamePk: number | null = null;

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
    void this.loadGame(this.gamePk);
  }

  private loadGame(gamePk: number): void {
    this.loading = true;
    this.loadError = false;
    this.refreshError = false;
    this.predictionRefreshMessage = null;
    this.predictionRefreshIsError = false;
    this.prediction = null;
    this.headToHead = [];
    this.api.getGame(gamePk).subscribe({
      next: (g) => {
        this.game = g;
        this.loading = false;
        if ('prediction' in g) {
          this.prediction = g.prediction ?? null;
          this.predLoading = false;
        } else {
          this.loadPrediction(gamePk);
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

  private loadPrediction(gamePk: number): void {
    this.predLoading = true;
    this.api.predict(gamePk).subscribe({
      next: (p) => {
        this.prediction = p;
        this.predLoading = false;
      },
      error: () => {
        this.prediction = null;
        this.predLoading = false;
      },
    });
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
            detail: this.api.getGame(pk).pipe(catchError(() => of(g))),
            pred: this.api.predict(pk).pipe(catchError(() => of(null))),
          });
        }),
      )
      .subscribe({
        next: ({ detail, pred }) => {
          this.game = detail;
          this.prediction = pred;
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
  favoriteBarProbability(): number | null {
    const p = this.prediction?.home_win_probability;
    if (p == null || Number.isNaN(p)) {
      return null;
    }
    return favoriteFromHomeWinProbability(p).favoriteWinProb;
  }

  favoriteVictoryLabel(): string {
    if (this.game == null) {
      return 'Victoria del favorito';
    }
    const { favorite, favoriteWinProb } = favoriteFromHomeWinProbability(
      this.prediction?.home_win_probability,
    );
    if (favorite === 'none' || favoriteWinProb == null) {
      return 'Victoria del favorito';
    }
    const team = favorite === 'home' ? this.game.home_team : this.game.away_team;
    return `Victoria ${this.abbr(team)}`;
  }

  hasRunsProjection(): boolean {
    const p = this.prediction;
    return (
      p != null &&
      typeof p.total_runs_estimate === 'number' &&
      Number.isFinite(p.total_runs_estimate) &&
      typeof p.over_under_line === 'number' &&
      Number.isFinite(p.over_under_line)
    );
  }

  runsEstimateFormatted(): string {
    const p = this.prediction;
    if (p == null || !this.hasRunsProjection()) {
      return '';
    }
    return this.formatRunNumber(p.total_runs_estimate);
  }

  ouLineFormatted(): string {
    const p = this.prediction;
    if (p == null || !this.hasRunsProjection()) {
      return '';
    }
    return this.formatRunNumber(p.over_under_line);
  }

  runsLeanLabel(): string {
    switch (this.runsLeanKind()) {
      case 'over':
        return 'Sobre';
      case 'under':
        return 'Bajo';
      default:
        return 'En la línea';
    }
  }

  runsLeanClass(): Record<string, boolean> {
    const k = this.runsLeanKind();
    return {
      'detail-lean-over': k === 'over',
      'detail-lean-under': k === 'under',
      'detail-lean-push': k === 'push',
    };
  }

  private runsLeanKind(): 'over' | 'under' | 'push' {
    const p = this.prediction;
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

  /** Solo estimación: no descarga calendario ni condiciones. */
  refreshPredictionOnly(): void {
    if (this.gamePk == null) {
      return;
    }
    this.predictionRefreshLoading = true;
    this.predictionRefreshMessage = null;
    this.predictionRefreshIsError = false;
    this.api.refreshPrediction(this.gamePk).subscribe({
      next: (p) => {
        this.prediction = p;
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
