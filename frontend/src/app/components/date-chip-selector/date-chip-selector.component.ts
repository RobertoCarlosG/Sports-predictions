import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { addDaysIso, consecutiveIsoDatesClamped, currentSeasonDateBounds } from '../../utils/date-bounds';

export type DateChipPreset = 'today' | 'tomorrow' | 'week';

export interface DateChipSelection {
  preset: DateChipPreset;
  dates: string[];
}

@Component({
  selector: 'app-date-chip-selector',
  standalone: true,
  imports: [MatButtonModule],
  templateUrl: './date-chip-selector.component.html',
  styleUrl: './date-chip-selector.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DateChipSelectorComponent implements OnInit {
  /** Fecha máxima permitida (típicamente hoy). Si no se pasa, se usa temporada en curso. */
  @Input() maxIso = '';

  @Input() minIso = '';

  @Output() readonly selectionChange = new EventEmitter<DateChipSelection>();

  preset: DateChipPreset = 'today';

  ngOnInit(): void {
    const b = currentSeasonDateBounds();
    if (!this.maxIso) {
      this.maxIso = b.max;
    }
    if (!this.minIso) {
      this.minIso = b.min;
    }
    this.emitPreset(this.preset);
  }

  select(p: DateChipPreset): void {
    this.preset = p;
    this.emitPreset(p);
  }

  private emitPreset(p: DateChipPreset): void {
    const dates = this.datesForPreset(p);
    this.selectionChange.emit({ preset: p, dates });
  }

  private datesForPreset(p: DateChipPreset): string[] {
    const max = this.maxIso;
    const min = this.minIso;
    if (p === 'today') {
      const d = max < min ? min : max;
      return [d];
    }
    if (p === 'tomorrow') {
      const base = max < min ? min : max;
      const iso = addDaysIso(base, 1);
      if (iso > max || iso < min) {
        return [base];
      }
      return [iso];
    }
    const start = max < min ? min : max;
    return consecutiveIsoDatesClamped(start, 7, max);
  }
}
