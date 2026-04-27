import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { addDaysIso, calendarWeekRangeClamped, currentSeasonDateBounds } from '../../utils/date-bounds';

export type DateChipPreset = 'today' | 'tomorrow' | 'week';

export interface DateChipSelection {
  preset: DateChipPreset;
  dates: string[];
}

/** Misma lógica que el selector de chips, para precargar desde la ruta (URL). */
export function buildDateSelectionForPreset(
  preset: DateChipPreset,
  minIso: string,
  maxIso: string,
): DateChipSelection {
  if (preset === 'today') {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, '0');
    const d = String(today.getDate()).padStart(2, '0');
    return { preset, dates: [`${y}-${m}-${d}`] };
  }
  if (preset === 'tomorrow') {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, '0');
    const d = String(today.getDate()).padStart(2, '0');
    const todayIso = `${y}-${m}-${d}`;
    return { preset, dates: [addDaysIso(todayIso, 1)] };
  }
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, '0');
  const d = String(today.getDate()).padStart(2, '0');
  const todayIso = `${y}-${m}-${d}`;
  return { preset, dates: calendarWeekRangeClamped(todayIso, minIso, maxIso) };
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

  preset = signal<DateChipPreset>('today');

  ngOnInit(): void {
    const b = currentSeasonDateBounds();
    if (!this.maxIso) {
      this.maxIso = b.max;
    }
    if (!this.minIso) {
      this.minIso = b.min;
    }
    this.emitPreset(this.preset());
  }

  select(p: DateChipPreset): void {
    this.preset.set(p);
    this.emitPreset(p);
  }

  private emitPreset(p: DateChipPreset): void {
    this.selectionChange.emit(buildDateSelectionForPreset(p, this.minIso, this.maxIso));
  }
}
