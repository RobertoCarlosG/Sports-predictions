import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

import { matchStatusKind, matchStatusLabel, type MatchStatusKind } from '../../utils/game-status';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  templateUrl: './status-badge.component.html',
  styleUrl: './status-badge.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatusBadgeComponent {
  /** Texto de estado del API (no se muestra tal cual al usuario). */
  @Input() apiStatus = '';

  /** Si se conoce el tipo, se puede fijar sin depender del texto del API. */
  @Input() kind?: MatchStatusKind;

  get resolvedKind(): MatchStatusKind {
    return this.kind ?? matchStatusKind(this.apiStatus);
  }

  get label(): string {
    return matchStatusLabel(this.resolvedKind);
  }
}
