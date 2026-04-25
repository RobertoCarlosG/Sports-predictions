import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { CommonModule } from '@angular/common';

import type { GameDetail, PredictionOut } from '../../models/game';
import type { HistoryGame } from '../../models/history';
import { mlbDisplayAbbrev } from '../../utils/mlb-team-abbr';
import { favoriteFromHomeWinProbability } from '../../utils/prediction-favorite';
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

  /**
   * Probabilidad del **favorito** (lado con mayor P de victoria) para alimentar la barra
   * (0–1, misma lógica que el API pero sin enmarcar «local/visitante»).
   */
  get favoriteBarProbability(): number | null | undefined {
    const ph = this.homeWinProbability;
    if (ph === undefined) {
      return undefined;
    }
    const { favoriteWinProb } = favoriteFromHomeWinProbability(ph);
    return favoriteWinProb;
  }

  get favoriteVictoryLabel(): string {
    const ph = this.homeWinProbability;
    const g = this.game as GameDetail;
    if (ph === undefined) {
      return 'Victoria del favorito';
    }
    const { favorite, favoriteWinProb } = favoriteFromHomeWinProbability(ph);
    if (favorite === 'none' || favoriteWinProb == null) {
      return 'Victoria del favorito';
    }
    const team = favorite === 'home' ? g.home_team : g.away_team;
    return `Victoria ${this.abbr(team)}`;
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

  /**
   * Solo mostramos acierto/fallo y bloque de evaluación si hubo pick explícito.
   * Sin `predicted_winner` el backend puede tener `is_correct`/`home_win_probability` incoherentes.
   */
  get showEvaluatedPick(): boolean {
    const pred = this.prediction;
    return (
      pred != null &&
      pred.predicted_winner != null &&
      pred.is_correct != null
    );
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
    if (!pred || pred.predicted_winner == null) {
      return '';
    }
    const ph = pred.home_win_probability;
    const pct =
      pred.predicted_winner === 'home'
        ? Math.round(ph * 100)
        : Math.round((1 - ph) * 100);
    const team = pred.predicted_winner === 'home' ? this.game.home_team : this.game.away_team;
    return `${pct}% a favor de ${this.abbr(team)}`;
  }

  /** Indicador O/U: backend envía `total_runs_estimate` y `over_under_line` (regresión + línea al .5). */
  get hasRunsLine(): boolean {
    const p = this.prediction;
    if (p == null) {
      return false;
    }
    return (
      typeof p.total_runs_estimate === 'number' &&
      Number.isFinite(p.total_runs_estimate) &&
      typeof p.over_under_line === 'number' &&
      Number.isFinite(p.over_under_line)
    );
  }

  /**
   * Comparación simple modelo vs línea: «Sobre» / «Bajo» / cerca (push).
   * Umbral mínimo para no marcar tendencia con diferencias mínimas de float.
   */
  get runsOuTendency(): 'over' | 'under' | 'push' {
    if (!this.hasRunsLine) {
      return 'push';
    }
    const p = this.prediction!;
    const d = p.total_runs_estimate - p.over_under_line;
    if (d > 0.02) {
      return 'over';
    }
    if (d < -0.02) {
      return 'under';
    }
    return 'push';
  }

  get runsOuTendencyLabel(): string {
    switch (this.runsOuTendency) {
      case 'over':
        return 'Sobre';
      case 'under':
        return 'Bajo';
      default:
        return 'En la línea';
    }
  }

  formatRunNumber(n: number): string {
    return n.toFixed(1).replace('.', ',');
  }

  get runsEstimateDisplay(): string {
    const p = this.prediction;
    if (p == null || !this.hasRunsLine) {
      return '';
    }
    return this.formatRunNumber(p.total_runs_estimate);
  }

  get ouLineDisplay(): string {
    const p = this.prediction;
    if (p == null || !this.hasRunsLine) {
      return '';
    }
    return this.formatRunNumber(p.over_under_line);
  }
}
