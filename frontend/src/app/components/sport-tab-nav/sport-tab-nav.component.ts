import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';

import { SPORT_OPTIONS, type SportId } from '../../models/sport';

@Component({
  selector: 'app-sport-tab-nav',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  templateUrl: './sport-tab-nav.component.html',
  styleUrl: './sport-tab-nav.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SportTabNavComponent {
  @Input() active: SportId = 'mlb';

  readonly sports = SPORT_OPTIONS;

  pathFor(id: SportId): string {
    switch (id) {
      case 'mlb':
        return '/mlb';
      case 'soccer':
        return '/soccer';
      case 'nba':
        return '/nba';
      default:
        return '/mlb';
    }
  }
}
