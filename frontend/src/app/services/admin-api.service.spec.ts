import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AdminApiService } from './admin-api.service';

describe('AdminApiService', () => {
  let service: AdminApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AdminApiService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AdminApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates', () => expect(service).toBeTruthy());

  it('starts logged out', () => {
    expect(service.isLoggedIn()).toBe(false);
  });

  it('authReady GET without credentials/headers', () => {
    service.authReady().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/auth/ready'));
    expect(req.request.method).toBe('GET');
    expect(req.request.withCredentials).toBeFalsy();
    req.flush({ login_available: true, detail: null });
  });

  it('checkSession GET sends credentials + X-Requested-With and sets sessionOk', () => {
    service.checkSession().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/auth/me'));
    expect(req.request.method).toBe('GET');
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.get('X-Requested-With')).toBe('XMLHttpRequest');
    req.flush({ username: 'admin' });
    expect(service.isLoggedIn()).toBe(true);
  });

  it('checkSession error clears sessionOk', () => {
    service.checkSession().subscribe({ error: () => undefined });
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/auth/me'));
    req.flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(service.isLoggedIn()).toBe(false);
  });

  it('login POST sets sessionOk and posts credentials body', () => {
    service.login('u', 'p').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/auth/login'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ username: 'u', password: 'p' });
    expect(req.request.withCredentials).toBe(true);
    req.flush({ username: 'u' });
    expect(service.isLoggedIn()).toBe(true);
  });

  it('logout POST clears sessionOk', () => {
    service.login('u', 'p').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/admin/auth/login')).flush({ username: 'u' });
    expect(service.isLoggedIn()).toBe(true);

    service.logout().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/auth/logout'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({ message: 'bye', detail: null });
    expect(service.isLoggedIn()).toBe(false);
  });

  it('clearSessionLocal flips sessionOk to false', () => {
    service.login('u', 'p').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/admin/auth/login')).flush({ username: 'u' });
    service.clearSessionLocal();
    expect(service.isLoggedIn()).toBe(false);
  });

  it('refreshSession POST', () => {
    service.refreshSession().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/auth/refresh'));
    expect(req.request.method).toBe('POST');
    req.flush({ username: 'u' });
  });

  it('status GET', () => {
    service.status().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/status'));
    expect(req.request.method).toBe('GET');
    req.flush({ message: 'ok', detail: null });
  });

  it('rebuildSnapshots POST normalizes empty season to null', () => {
    service.rebuildSnapshots('', 30).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/rebuild-snapshots'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ season: null, window: 30 });
    req.flush({ message: 'ok', detail: null });
  });

  it('clearPredictionCache POST', () => {
    service.clearPredictionCache().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/clear-prediction-cache'));
    expect(req.request.method).toBe('POST');
    req.flush({ message: 'ok', detail: null });
  });

  it('fixFifty POST', () => {
    service.fixFifty().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/fix-fifty'));
    expect(req.request.method).toBe('POST');
    req.flush({ message: 'ok', detail: null });
  });

  it('reloadModel POST', () => {
    service.reloadModel().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/model/reload'));
    expect(req.request.method).toBe('POST');
    req.flush({ message: 'ok', detail: null });
  });

  it('reloadModelXgb POST', () => {
    service.reloadModelXgb().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/model/reload-xgb'));
    expect(req.request.method).toBe('POST');
    req.flush({ message: 'ok', detail: null });
  });

  it('calibrateModel POST maps response to message + detail', () => {
    let result: { message: string; detail: string | null } | undefined;
    service.calibrateModel().subscribe((r) => (result = r));
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/model/calibrate'));
    expect(req.request.method).toBe('POST');
    req.flush({
      message: 'done',
      model_version: 'v1',
      n_samples: 42,
      calibration_path: '/tmp/x',
    });
    expect(result).toEqual({
      message: 'done',
      detail: 'Modelo: v1 — 42 partidos evaluados',
    });
  });

  it('trainModel POST forwards body', () => {
    const body = { season: '2024', trees: 100 };
    service.trainModel(body).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/train'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({ message: 'ok', stdout_tail: null });
  });

  it('backfill POST maps params to snake_case body', () => {
    service.backfill('2024-01-01', '2024-01-31', true, 2).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/backfill'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      start: '2024-01-01',
      end: '2024-01-31',
      fetch_details: true,
      sleep_s: 2,
    });
    req.flush({ message: 'ok', detail: null });
  });

  it('getBackfillStatus GET', () => {
    service.getBackfillStatus().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/backfill-status'));
    expect(req.request.method).toBe('GET');
    req.flush({ status: 'idle', job_id: null, days_total: 0, days_done: 0 });
  });

  it('runMlbDailySnapshot POST sends low_memory flag', () => {
    service.runMlbDailySnapshot(true).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/mlb-daily-snapshot'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ low_memory: true });
    req.flush({ message: 'ok', detail: null });
  });

  it('runMlbDailySnapshot defaults low_memory to false', () => {
    service.runMlbDailySnapshot().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/pipeline/mlb-daily-snapshot'));
    expect(req.request.body).toEqual({ low_memory: false });
    req.flush({ message: 'ok', detail: null });
  });

  it('getBacktestReport GET sets query params', () => {
    service
      .getBacktestReport({
        dateFrom: '2024-01-01',
        dateTo: '2024-01-31',
        minConfidence: 0.6,
        skipEmptyDays: true,
      })
      .subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/predictions/backtest'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('date_from')).toBe('2024-01-01');
    expect(req.request.params.get('date_to')).toBe('2024-01-31');
    expect(req.request.params.get('min_confidence')).toBe('0.6');
    expect(req.request.params.get('skip_empty_days')).toBe('true');
    req.flush({
      date_from: '2024-01-01',
      date_to: '2024-01-31',
      min_confidence: 0.6,
      skip_empty_days: true,
      summary: {},
      timeseries: [],
      games: [],
    });
  });

  it('getBacktestReport caches by key (second call does not re-hit http)', () => {
    const p = {
      dateFrom: '2024-01-01',
      dateTo: '2024-01-31',
      minConfidence: 0.6,
      skipEmptyDays: true,
    };
    service.getBacktestReport(p).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/admin/predictions/backtest'));
    req.flush({
      date_from: '2024-01-01',
      date_to: '2024-01-31',
      min_confidence: 0.6,
      skip_empty_days: true,
      summary: {},
      timeseries: [],
      games: [],
    });
    // Second call with same key: served from cache, no new request.
    service.getBacktestReport(p).subscribe();
    httpMock.expectNone((r) => r.url.endsWith('/admin/predictions/backtest'));
  });
});
