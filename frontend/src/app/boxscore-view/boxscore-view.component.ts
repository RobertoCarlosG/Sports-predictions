import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
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
})
export class BoxscoreViewComponent {
  @Input({ required: true }) boxscore!: Record<string, unknown> | null;

  get summary(): BoxscoreSummary | null {
    return parseBoxscoreSummary(this.boxscore);
  }

  cell(v: number | null): string {
    return v === null || v === undefined ? '—' : String(v);
  }
}
