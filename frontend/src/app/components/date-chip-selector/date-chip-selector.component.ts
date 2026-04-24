import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { addDaysIso, calendarWeekRangeClamped, currentSeasonDateBounds } from '../../utils/date-bounds';

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
      const today = new Date();
      const y = today.getFullYear();
      const m = String(today.getMonth() + 1).padStart(2, '0');
      const d = String(today.getDate()).padStart(2, '0');
      return [`${y}-${m}-${d}`];
    }
    if (p === 'tomorrow') {
      const today = new Date();
      const y = today.getFullYear();
      const m = String(today.getMonth() + 1).padStart(2, '0');
      const d = String(today.getDate()).padStart(2, '0');
      const todayIso = `${y}-${m}-${d}`;
      const iso = addDaysIso(todayIso, 1);
      return [iso];
    }
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, '0');
    const d = String(today.getDate()).padStart(2, '0');
    const todayIso = `${y}-${m}-${d}`;
    return calendarWeekRangeClamped(todayIso, min, max);
  }
}
