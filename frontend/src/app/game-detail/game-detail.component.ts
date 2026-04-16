import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import type { GameDetail, PredictionOut } from '../models/game';
import { GamesApiService } from '../services/games-api.service';
import { parseApiError, type ApiErrorView } from '../utils/api-error';

@Component({
  selector: 'app-game-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatDividerModule,
    MatExpansionModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './game-detail.component.html',
  styleUrl: './game-detail.component.scss',
})
export class GameDetailComponent implements OnInit {
  private readonly api = inject(GamesApiService);
  private readonly route = inject(ActivatedRoute);

  game: GameDetail | null = null;
  prediction: PredictionOut | null = null;
  loading = false;
  predLoading = false;
  weatherLoading = false;
  errorView: ApiErrorView | null = null;

  ngOnInit(): void {
    this.route.paramMap.subscribe((pm) => {
      const pk = pm.get('gamePk');
      if (!pk) {
        this.errorView = {
          title: 'Ruta no válida',
          summary: 'Falta el identificador del partido.',
          hints: ['Vuelve al listado e intenta abrir un partido de nuevo.'],
          httpStatus: 0,
        };
        return;
      }
      void this.loadGame(Number(pk));
    });
  }

  private loadGame(gamePk: number): void {
    this.loading = true;
    this.errorView = null;
    this.prediction = null;
    this.api.getGame(gamePk).subscribe({
      next: (g) => {
        this.game = g;
        this.loading = false;
        this.loadPrediction(gamePk);
      },
      error: (e: unknown) => {
        this.loading = false;
        this.errorView = parseApiError(e);
      },
    });
  }

  loadPrediction(gamePk: number): void {
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

  hasScore(g: GameDetail): boolean {
    return typeof g.away_score === 'number' && typeof g.home_score === 'number';
  }

  refreshWeather(): void {
    if (!this.game) {
      return;
    }
    this.weatherLoading = true;
    this.api.refreshWeather(this.game.game_pk).subscribe({
      next: (g) => {
        this.game = g;
        this.weatherLoading = false;
        this.loadPrediction(g.game_pk);
      },
      error: () => {
        this.weatherLoading = false;
      },
    });
  }
}
