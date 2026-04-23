import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';

import type { GameDetail } from '../../models/game';
import type { HistoryGame } from '../../models/history';
import { mlbDisplayAbbrev } from '../../utils/mlb-team-abbr';
import { ProbabilityBarComponent } from '../probability-bar/probability-bar.component';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';
import { WeatherChipComponent } from '../weather-chip/weather-chip.component';

@Component({
  selector: 'app-match-card',
  standalone: true,
  imports: [
    RouterLink,
    MatCardModule,
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
}
