import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { BacktestDashboardComponent } from './backtest-dashboard.component';
import {
  AdminApiService,
  type BacktestGameRow,
  type BacktestResponse,
} from '../services/admin-api.service';

function makeRow(overrides: Partial<BacktestGameRow> = {}): BacktestGameRow {
  return {
    game_pk: 778899,
    game_date: '2026-06-10',
    game_datetime_utc: '2026-06-10T23:05:00Z',
    away_abbr: 'NYY',
    home_abbr: 'BOS',
    matchup_label: 'NYY @ BOS',
    p_home: 0.62,
    ml_confidence: 0.62,
    predicted_winner: 'home',
    actual_winner: 'home',
    ml_correct: true,
    over_under_line: 8.5,
    total_runs_estimate: 9.1,
    predicted_ou: 'over',
    total_runs_actual: 10,
    ou_outcome: 'win',
    ou_correct: true,
    success_count: 2,
    success_label: 'ML ✓ · O/U ✓',
    ...overrides,
  };
}

function makeResponse(): BacktestResponse {
  return {
    date_from: '2026-05-11',
    date_to: '2026-06-10',
    min_confidence: 0.55,
    skip_empty_days: true,
    summary: {
      n_games: 2,
      ml_wins: 1,
      ml_losses: 1,
      ou_wins: 1,
      ou_losses: 0,
      ou_pushes: 1,
      global_hit_rate_pct: 66.7,
      total_decided_picks: 3,
      total_correct_picks: 2,
    },
    timeseries: [
      {
        game_date: '2026-06-09',
        games_count: 1,
        ml_hit_rate_pct: 100,
        ou_hit_rate_pct: 50,
        ou_decided: 1,
      },
      {
        game_date: '2026-06-10',
        games_count: 1,
        ml_hit_rate_pct: null,
        ou_hit_rate_pct: null,
        ou_decided: 0,
      },
    ],
    games: [makeRow()],
  };
}

describe('BacktestDashboardComponent', () => {
  let fixture: ComponentFixture<BacktestDashboardComponent>;
  let component: BacktestDashboardComponent;
  let adminSpy: jasmine.SpyObj<AdminApiService>;
  let response: BacktestResponse;

  beforeEach(async () => {
    response = makeResponse();
    adminSpy = jasmine.createSpyObj<AdminApiService>('AdminApiService', [
      'getBacktestReport',
    ]);
    adminSpy.getBacktestReport.and.returnValue(of(response));

    await TestBed.configureTestingModule({
      imports: [BacktestDashboardComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AdminApiService, useValue: adminSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(BacktestDashboardComponent);
    component = fixture.componentInstance;
  });

  it('creates without rendering the chart', () => {
    expect(component).toBeTruthy();
  });

  it('ngOnInit seeds the date range and loads the report', () => {
    component.ngOnInit();
    expect(component.dateFrom).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(component.dateTo).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(adminSpy.getBacktestReport).toHaveBeenCalledTimes(1);
    expect(component.report).toBe(response);
    expect(component.loading).toBeFalse();
    expect(component.error).toBeNull();
  });

  it('load builds chart datasets from the timeseries', () => {
    component.load();
    expect(component.chartData.labels).toEqual(['2026-06-09', '2026-06-10']);
    expect(component.chartData.datasets.length).toBe(2);
    expect(component.chartData.datasets[0].label).toBe('Moneyline (%)');
    expect(component.chartData.datasets[0].data).toEqual([100, null]);
    expect(component.chartData.datasets[1].label).toBe('O/U (%)');
    expect(component.chartData.datasets[1].data).toEqual([50, null]);
  });

  it('load surfaces an error message on failure', () => {
    adminSpy.getBacktestReport.and.returnValue(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ({ subscribe: (obs: any) => obs.error({ error: { detail: 'Rango inválido' } }) }) as any,
    );
    component.load();
    expect(component.loading).toBeFalse();
    expect(component.error).toBe('Rango inválido');
  });

  it('refresh forces a non-cached reload', () => {
    component.refresh();
    const lastCall = adminSpy.getBacktestReport.calls.mostRecent();
    expect(lastCall.args[1]).toEqual({ force: true });
  });

  it('onConfidenceSliderChange debounces and triggers a load', fakeAsync(() => {
    component.ngOnInit();
    adminSpy.getBacktestReport.calls.reset();

    component.minConfidence = 0.7;
    component.onConfidenceSliderChange();
    tick(400);

    expect(adminSpy.getBacktestReport).toHaveBeenCalledTimes(1);
    component.ngOnDestroy();
  }));

  it('sideAbbr returns the abbreviation for each side', () => {
    const row = makeRow();
    expect(component.sideAbbr(row, 'home')).toBe('BOS');
    expect(component.sideAbbr(row, 'away')).toBe('NYY');
  });

  it('mlPredLabel formats the predicted side and confidence', () => {
    expect(component.mlPredLabel(makeRow())).toBe('BOS 62%');
  });

  it('mlActualLabel renders the winning abbr and handles ties', () => {
    expect(component.mlActualLabel(makeRow({ actual_winner: 'away' }))).toBe('NYY');
    expect(component.mlActualLabel(makeRow({ actual_winner: 'tie' }))).toBe('Empate');
  });

  it('ouPredLabel formats over and under with the line', () => {
    expect(component.ouPredLabel(makeRow({ predicted_ou: 'over' }))).toBe('Over 8.5');
    expect(component.ouPredLabel(makeRow({ predicted_ou: 'under' }))).toBe('Under 8.5');
  });

  it('exportCsv is a no-op when there are no games', () => {
    component.report = { ...makeResponse(), games: [] };
    const spy = spyOn(document, 'createElement').and.callThrough();
    component.exportCsv();
    expect(spy).not.toHaveBeenCalled();
  });

  it('exportCsv triggers a download when games exist', () => {
    component.report = makeResponse();
    const anchor = document.createElement('a');
    const clickSpy = spyOn(anchor, 'click');
    spyOn(document, 'createElement').and.returnValue(anchor);
    spyOn(URL, 'createObjectURL').and.returnValue('blob:fake');
    spyOn(URL, 'revokeObjectURL');

    component.exportCsv();

    expect(clickSpy).toHaveBeenCalled();
    expect(anchor.download).toContain('backtest-');
  });
});
