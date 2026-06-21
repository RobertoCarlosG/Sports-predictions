import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, of, switchMap } from 'rxjs';

import { ProbabilityBarComponent } from '../../components/probability-bar/probability-bar.component';
import { StatusBadgeComponent } from '../../components/status-badge/status-badge.component';
import type { NbaGameDetail, NbaModelKind, NbaPredictionOut } from '../../models/nba';
import { favoriteFromHomeWinProbability } from '../../utils/prediction-favorite';
import { GamesApiService } from '../../services/games-api.service';

const MODELS: NbaModelKind[] = ['xgb', 'lgbm', 'catboost', 'ensemble'];

@Component({
  selector: 'app-nba-game-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatIconModule,
    MatProgressSpinnerModule,
    ProbabilityBarComponent,
    StatusBadgeComponent,
  ],
  templateUrl: './nba-game-detail.component.html',
  styleUrl: './nba-game-detail.component.scss',
})
export class NbaGameDetailComponent {
  private readonly api = inject(GamesApiService);
  private readonly route = inject(ActivatedRoute);

  readonly models = MODELS;
  game = signal<NbaGameDetail | null>(null);
  prediction = signal<NbaPredictionOut | null>(null);
  selectedModel = signal<NbaModelKind>('xgb');
  loading = signal(true);
  loadError = signal(false);
  predLoading = signal(false);

  private gameId = '';

  readonly favoriteLabel = computed(() => {
    const g = this.game();
    const p = this.prediction();
    if (!g || !p) {
      return 'Victoria del favorito';
    }
    const { favorite } = favoriteFromHomeWinProbability(p.home_win_probability);
    if (favorite === 'none') {
      return 'Victoria del favorito';
    }
    const team = favorite === 'home' ? g.home_team : g.away_team;
    return `Victoria ${team.abbreviation}`;
  });

  readonly favoriteProb = computed(() => {
    const p = this.prediction();
    return p ? favoriteFromHomeWinProbability(p.home_win_probability).favoriteWinProb : null;
  });

  constructor() {
    this.route.paramMap
      .pipe(
        switchMap((pm) => {
          this.gameId = pm.get('gameId') ?? '';
          this.loading.set(true);
          this.loadError.set(false);
          return this.api.getNbaGame(this.gameId).pipe(catchError(() => of(null)));
        }),
        takeUntilDestroyed(),
      )
      .subscribe((g) => {
        this.loading.set(false);
        if (g == null) {
          this.loadError.set(true);
          return;
        }
        this.game.set(g);
        this.prediction.set(g.prediction ?? null);
      });
  }

  fmt(n: number | null | undefined): string {
    return typeof n === 'number' ? n.toFixed(1).replace('.', ',') : '—';
  }

  pct(n: number | null | undefined): string {
    return typeof n === 'number' ? `${Math.round(n * 100)}%` : '—';
  }

  selectModel(model: NbaModelKind): void {
    if (model === this.selectedModel() && this.prediction()) {
      return;
    }
    this.selectedModel.set(model);
    this.predLoading.set(true);
    this.api
      .predictNba(this.gameId, { model })
      .pipe(catchError(() => of(null)))
      .subscribe((p) => {
        this.predLoading.set(false);
        if (p != null) {
          this.prediction.set(p);
        }
      });
  }
}
