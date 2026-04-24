import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { CommonModule } from '@angular/common';

import type { GameDetail, PredictionOut } from '../../models/game';
import type { HistoryGame } from '../../models/history';
import { mlbDisplayAbbrev } from '../../utils/mlb-team-abbr';
import { ProbabilityBarComponent } from '../probability-bar/probability-bar.component';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';
import { WeatherChipComponent } from '../weather-chip/weather-chip.component';

@Component({
  selector: 'app-match-card',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatIconModule,
    StatusBadgeComponent,
    WeatherChipComponent,
    ProbabilityBarComponent,
  ],
  templateUrl: './match-card.component.html',
  styleUrl: './match-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MatchCardComponent {
  @Input({ required: true }) game!: GameDetail | HistoryGame;
  /** Fracción 0–1 victoria local; null/undefined muestra barra «Sin datos». */
  @Input() homeWinProbability: number | null | undefined;

  abbr(team: GameDetail['away_team']): string {
    return mlbDisplayAbbrev(team);
  }

  hasScore(): boolean {
    const g = this.game;
    return typeof g.away_score === 'number' && typeof g.home_score === 'number';
  }

  get weather(): Record<string, unknown> | null | undefined {
    const g = this.game as GameDetail;
    return g.weather ?? undefined;
  }

  get prediction(): PredictionOut | null | undefined {
    const g = this.game as GameDetail;
    return g.prediction;
  }

  get hasPrediction(): boolean {
    return this.prediction != null;
  }

  get isEvaluated(): boolean {
    const pred = this.prediction;
    return pred != null && pred.is_correct != null;
  }

  get predictionCorrect(): boolean {
    return this.prediction?.is_correct === true;
  }

  get predictionIncorrect(): boolean {
    return this.prediction?.is_correct === false;
  }

  get predictedWinnerLabel(): string {
    const pred = this.prediction;
    if (!pred || !pred.predicted_winner) return '';
    if (pred.predicted_winner === 'home') {
      return `Victoria ${this.abbr(this.game.home_team)}`;
    }
    return `Victoria ${this.abbr(this.game.away_team)}`;
  }

  get actualWinnerLabel(): string {
    const pred = this.prediction;
    if (!pred || !pred.actual_winner) return '';
    if (pred.actual_winner === 'home') {
      return `Ganó ${this.abbr(this.game.home_team)}`;
    }
    if (pred.actual_winner === 'away') {
      return `Ganó ${this.abbr(this.game.away_team)}`;
    }
    return 'Empate';
  }

  get confidencePercent(): string {
    const pred = this.prediction;
    if (!pred) return '';
    const percent = Math.round(pred.home_win_probability * 100);
    if (pred.predicted_winner === 'home') {
      return `${percent}% confianza`;
    }
    return `${100 - percent}% confianza`;
  }
}
