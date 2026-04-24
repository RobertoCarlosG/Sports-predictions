import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Probabilidad local en fracción 0–1, como en el API. */
@Component({
  selector: 'app-probability-bar',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './probability-bar.component.html',
  styleUrl: './probability-bar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProbabilityBarComponent {
  readonly probability = input<number | null | undefined>(undefined);
  readonly label = input<string>('Victoria local');
  /** Cuando no hay fracción (partido sin estimación, ver ``Comportamiento-predicciones``). */
  readonly noDataText = input<string>('Sin predicción');

  readonly pct = computed(() => {
    const p = this.probability();
    if (p == null || Number.isNaN(p)) {
      return null;
    }
    return Math.round(Math.min(1, Math.max(0, p)) * 1000) / 10;
  });

  readonly barWidth = computed(() => {
    const p = this.pct();
    if (p == null) {
      return 0;
    }
    return p;
  });

  readonly toneClass = computed(() => {
    const p = this.pct();
    if (p == null) {
      return 'tone-muted';
    }
    if (p > 65) {
      return 'tone-high';
    }
    if (p >= 40) {
      return 'tone-mid';
    }
    return 'tone-low';
  });
}
