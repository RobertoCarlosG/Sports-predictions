import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import type { GameDetail, PredictionOut } from '../models/game';
import { GamesApiService } from '../services/games-api.service';

@Component({
  selector: 'app-game-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
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
  error: string | null = null;

  ngOnInit(): void {
    this.route.paramMap.subscribe((pm) => {
      const pk = pm.get('gamePk');
      if (!pk) {
        this.error = 'Partido no encontrado';
        return;
      }
      void this.loadGame(Number(pk));
    });
  }

  private loadGame(gamePk: number): void {
    this.loading = true;
    this.error = null;
    this.prediction = null;
    this.api.getGame(gamePk).subscribe({
      next: (g) => {
        this.game = g;
        this.loading = false;
        this.loadPrediction(gamePk);
      },
      error: (e: unknown) => {
        this.loading = false;
        this.error = e instanceof Error ? e.message : 'No se pudo cargar el partido';
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
