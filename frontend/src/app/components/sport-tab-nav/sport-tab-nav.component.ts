import { ChangeDetectionStrategy, Component, Input, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';

import { SPORT_OPTIONS, type SportId } from '../../models/sport';
import { FeaturesService } from '../../services/features.service';

@Component({
  selector: 'app-sport-tab-nav',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  templateUrl: './sport-tab-nav.component.html',
  styleUrl: './sport-tab-nav.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SportTabNavComponent {
  private readonly featuresSvc = inject(FeaturesService);

  @Input() active: SportId | null = 'mlb';

  readonly sports = computed(() =>
    SPORT_OPTIONS.map((s) =>
      s.id === 'nba' ? { ...s, implemented: this.featuresSvc.nbaEnabled() } : s,
    ),
  );

  pathFor(id: SportId): string {
    switch (id) {
      case 'mlb':
        return '/mlb/today';
      case 'soccer':
        return '/soccer';
      case 'nba':
        return '/nba';
      default:
        return '/mlb/today';
    }
  }
}
