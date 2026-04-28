import { CommonModule, formatDate } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSliderModule } from '@angular/material/slider';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { BaseChartDirective } from 'ng2-charts';
import { ChartConfiguration, ChartData } from 'chart.js';
import { Subject, Subscription, debounceTime, distinctUntilChanged } from 'rxjs';

import {
  AdminApiService,
  type BacktestGameRow,
  type BacktestResponse,
} from '../services/admin-api.service';

import * as ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

@Component({
  selector: 'app-backtest-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
    MatSliderModule,
    MatTableModule,
    MatTooltipModule,
    BaseChartDirective,
  ],
  templateUrl: './backtest-dashboard.component.html',
  styleUrl: './backtest-dashboard.component.scss',
})
export class BacktestDashboardComponent implements OnInit, OnDestroy {
  private readonly admin = inject(AdminApiService);

  private readonly confidence$ = new Subject<number>();
  private confSub: Subscription | null = null;

  dateFrom = '';
  dateTo = '';
  minConfidence = 0.55;
  skipEmptyDays = true;

  loading = false;
  error: string | null = null;
  report: BacktestResponse | null = null;

  displayedColumns: string[] = [
    'when',
    'matchup',
    'ml',
    'ou',
    'overall',
  ];

  chartType = 'line' as const;
  chartData: ChartData<'line'> = { labels: [], datasets: [] };
  chartOptions: ChartConfiguration['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        min: 0,
        max: 100,
        ticks: { callback: (v) => `${v}%` },
      },
    },
    plugins: {
      legend: { display: true, position: 'top' },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const v = ctx.raw as number | null;
            if (v == null || Number.isNaN(v)) {
              return `${ctx.dataset.label}: —`;
            }
            return `${ctx.dataset.label}: ${v}%`;
          },
        },
      },
    },
  };

  ngOnInit(): void {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 30);
    this.dateTo = formatDate(end, 'yyyy-MM-dd', 'en-CA');
    this.dateFrom = formatDate(start, 'yyyy-MM-dd', 'en-CA');

    this.confSub = this.confidence$
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(() => this.load());

    this.load();
  }

  ngOnDestroy(): void {
    this.confSub?.unsubscribe();
  }

  onConfidenceSliderChange(): void {
    this.confidence$.next(this.minConfidence);
  }

  load(): void {
    this.loading = true;
    this.error = null;
    this.admin
      .getBacktestReport({
        dateFrom: this.dateFrom,
        dateTo: this.dateTo,
        minConfidence: this.minConfidence,
        skipEmptyDays: this.skipEmptyDays,
      })
      .subscribe({
        next: (r) => {
          this.report = r;
          this.applyChartData(r);
          this.loading = false;
        },
        error: (err) => {
          this.loading = false;
          this.error = this.formatLoadError(err);
        },
      });
  }

  private applyChartData(r: BacktestResponse): void {
    const labels = r.timeseries.map((t) => t.game_date);
    this.chartData = {
      labels,
      datasets: [
        {
          label: 'Moneyline (%)',
          data: r.timeseries.map((t) => t.ml_hit_rate_pct),
          borderColor: '#1976d2',
          backgroundColor: 'rgba(25, 118, 210, 0.12)',
          fill: false,
          tension: 0.2,
          spanGaps: true,
        },
        {
          label: 'O/U (%)',
          data: r.timeseries.map((t) => t.ou_hit_rate_pct),
          borderColor: '#2e7d32',
          backgroundColor: 'rgba(46, 125, 50, 0.1)',
          fill: false,
          tension: 0.2,
          spanGaps: true,
        },
      ],
    };
  }

  sideAbbr(row: BacktestGameRow, side: 'home' | 'away'): string {
    return side === 'home' ? row.home_abbr : row.away_abbr;
  }

  mlPredLabel(row: BacktestGameRow): string {
    return `${this.sideAbbr(row, row.predicted_winner)} ${(row.ml_confidence * 100).toFixed(0)}%`;
  }

  mlActualLabel(row: BacktestGameRow): string {
    if (row.actual_winner === 'tie') {
      return 'Empate';
    }
    return this.sideAbbr(row, row.actual_winner);
  }

  ouPredLabel(row: BacktestGameRow): string {
    return `${row.predicted_ou === 'over' ? 'Over' : 'Under'} ${row.over_under_line}`;
  }

  exportCsv(): void {
    const g = this.report?.games;
    if (!g?.length) {
      return;
    }
    const flat = g.map((row) => ({
      game_pk: row.game_pk,
      game_date: row.game_date,
      game_datetime_utc: row.game_datetime_utc,
      matchup: row.matchup_label,
      p_home: row.p_home,
      ml_confidence: row.ml_confidence,
      predicted_winner: row.predicted_winner,
      actual_winner: row.actual_winner,
      ml_correct: row.ml_correct,
      predicted_ou: row.predicted_ou,
      over_under_line: row.over_under_line,
      total_runs_actual: row.total_runs_actual,
      ou_outcome: row.ou_outcome,
      ou_correct: row.ou_correct,
      success_label: row.success_label,
    }));
    const headers = Object.keys(flat[0]);
    const lines = [headers.join(','), ...flat.map((o) => headers.map((h) => this.csvEscape((o as any)[h])).join(','))];
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    this.triggerDownload(blob, `backtest-${this.dateFrom}-${this.dateTo}.csv`);
  }

  async exportXlsx(): Promise<void> {
    const g = this.report?.games;
    if (!g?.length) {
      return;
    }
    const flat = g.map((row) => ({
      game_pk: row.game_pk,
      game_date: row.game_date,
      game_datetime_utc: row.game_datetime_utc,
      matchup: row.matchup_label,
      p_home: row.p_home,
      ml_confidence: row.ml_confidence,
      predicted_winner: row.predicted_winner,
      actual_winner: row.actual_winner,
      ml_correct: row.ml_correct,
      predicted_ou: row.predicted_ou,
      over_under_line: row.over_under_line,
      total_runs_actual: row.total_runs_actual,
      ou_outcome: row.ou_outcome,
      ou_correct: row.ou_correct,
      success_label: row.success_label,
    }));
    
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Backtest');
    
    const headers = Object.keys(flat[0]);
    worksheet.addRow(headers);
    
    flat.forEach(row => {
      worksheet.addRow(Object.values(row));
    });
    
    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, `backtest-${this.dateFrom}-${this.dateTo}.xlsx`);
  }

  private csvEscape(v: unknown): string {
    if (v === null || v === undefined) {
      return '';
    }
    const s = String(v);
    if (/[",\n]/.test(s)) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  }

  private triggerDownload(blob: Blob, name: string): void {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  private formatLoadError(err: unknown): string {
    const d = (err as { error?: { detail?: string | { msg: string }[] } })?.error?.detail;
    if (Array.isArray(d) && d[0]) {
      return String((d[0] as { msg?: string }).msg ?? d[0]);
    }
    if (typeof d === 'string') {
      return d;
    }
    return (err as Error)?.message ?? 'Error al cargar el backtest';
  }
}
