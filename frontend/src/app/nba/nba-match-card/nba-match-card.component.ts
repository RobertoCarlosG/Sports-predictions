import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

import type { NbaGameDetail, NbaPredictionOut } from '../../models/nba';
import { favoriteFromHomeWinProbability } from '../../utils/prediction-favorite';
import { ProbabilityBarComponent } from '../../components/probability-bar/probability-bar.component';
import { StatusBadgeComponent } from '../../components/status-badge/status-badge.component';

@Component({
  selector: 'app-nba-match-card',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatIconModule,
    MatTooltipModule,
    StatusBadgeComponent,
    ProbabilityBarComponent,
  ],
  templateUrl: './nba-match-card.component.html',
  styleUrl: './nba-match-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NbaMatchCardComponent {
  @Input({ required: true }) game!: NbaGameDetail;
  @Input() homeWinProbability: number | null | undefined;

  get prediction(): NbaPredictionOut | null | undefined {
    return this.game.prediction;
  }

  get insufficientData(): boolean {
    return this.prediction?.defaults_injected === true;
  }

  hasScore(): boolean {
    return typeof this.game.away_score === 'number' && typeof this.game.home_score === 'number';
  }

  get favoriteBarProbability(): number | null | undefined {
    const ph = this.homeWinProbability;
    if (ph === undefined) {
      return undefined;
    }
    return favoriteFromHomeWinProbability(ph).favoriteWinProb;
  }

  get favoriteVictoryLabel(): string {
    const ph = this.homeWinProbability;
    if (ph === undefined) {
      return 'Victoria del favorito';
    }
    const { favorite } = favoriteFromHomeWinProbability(ph);
    if (favorite === 'none') {
      return 'Victoria del favorito';
    }
    const team = favorite === 'home' ? this.game.home_team : this.game.away_team;
    return `Victoria ${team.abbreviation}`;
  }

  get hasTotals(): boolean {
    const p = this.prediction;
    return (
      p != null &&
      Number.isFinite(p.total_points_estimate) &&
      Number.isFinite(p.over_under_line)
    );
  }

  private fmt(n: number): string {
    return n.toFixed(1).replace('.', ',');
  }

  get totalEstimateDisplay(): string {
    return this.hasTotals ? this.fmt(this.prediction!.total_points_estimate) : '';
  }

  get ouLineDisplay(): string {
    return this.hasTotals ? this.fmt(this.prediction!.over_under_line) : '';
  }

  get ouTendency(): 'over' | 'under' | 'push' {
    if (!this.hasTotals) {
      return 'push';
    }
    const d = this.prediction!.total_points_estimate - this.prediction!.over_under_line;
    if (d > 0.05) {
      return 'over';
    }
    if (d < -0.05) {
      return 'under';
    }
    return 'push';
  }

  get ouTendencyLabel(): string {
    switch (this.ouTendency) {
      case 'over':
        return 'Sobre';
      case 'under':
        return 'Bajo';
      default:
        return 'En la línea';
    }
  }

  get spreadDisplay(): string {
    const p = this.prediction;
    if (p == null || !Number.isFinite(p.spread_line)) {
      return '';
    }
    const fav = p.spread_line <= 0 ? this.game.home_team : this.game.away_team;
    const line = Math.abs(p.spread_line);
    return `${fav.abbreviation} ${this.fmt(-line)}`;
  }
}
