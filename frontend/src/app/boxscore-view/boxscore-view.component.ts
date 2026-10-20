import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { MatExpansionModule } from '@angular/material/expansion';

import {
  parseBoxscoreSummary,
  type BoxscoreSummary,
} from '../utils/boxscore-parse';

@Component({
  selector: 'app-boxscore-view',
  standalone: true,
  imports: [CommonModule, MatExpansionModule],
  templateUrl: './boxscore-view.component.html',
  styleUrl: './boxscore-view.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BoxscoreViewComponent {
  private boxscoreValue: Record<string, unknown> | null = null;
  private parsedSummary: BoxscoreSummary | null = null;

  /**
   * Se parsea una sola vez por cambio de input. Antes un getter re-parseaba el payload en cada
   * ciclo de detección y devolvía un objeto nuevo, re-evaluando toda la tabla de entradas.
   */
  @Input({ required: true })
  set boxscore(value: Record<string, unknown> | null) {
    this.boxscoreValue = value;
    this.parsedSummary = parseBoxscoreSummary(value);
  }

  get boxscore(): Record<string, unknown> | null {
    return this.boxscoreValue;
  }

  get summary(): BoxscoreSummary | null {
    return this.parsedSummary;
  }

  cell(v: number | null): string {
    return v === null || v === undefined ? '—' : String(v);
  }
}
