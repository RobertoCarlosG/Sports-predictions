import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { DEFAULT_ML_MODEL, GamesApiService } from './games-api.service';

describe('GamesApiService', () => {
  let service: GamesApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [GamesApiService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(GamesApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates', () => expect(service).toBeTruthy());

  it('listGames GET sets date/sync/fetch_details/include_predictions', () => {
    service.listGames('2024-06-01').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/games'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('date')).toBe('2024-06-01');
    expect(req.request.params.get('sync')).toBe('true');
    expect(req.request.params.get('fetch_details')).toBe('true');
    expect(req.request.params.get('include_predictions')).toBe('true');
    req.flush({});
  });

  it('listGames honors includePredictions=false', () => {
    service.listGames('2024-06-01', false, { includePredictions: false }).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/games'));
    expect(req.request.params.get('sync')).toBe('false');
    expect(req.request.params.get('include_predictions')).toBe('false');
    req.flush({});
  });

  it('listGames caches by key (no second http hit)', () => {
    service.listGames('2024-06-01').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/games')).flush({});
    service.listGames('2024-06-01').subscribe();
    httpMock.expectNone((r) => r.url.endsWith('/games'));
  });

  it('getGame GET to /games/:pk with include_predictions', () => {
    service.getGame(777).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/games/777'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('include_predictions')).toBe('true');
    req.flush({});
  });

  it('refreshWeather POST to /games/:pk/weather', () => {
    service.refreshWeather(777).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/games/777/weather'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({});
  });

  it('predict GET omits model param when default (xgb)', () => {
    service.predict(123).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/predict/123'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.has('model')).toBe(false);
    req.flush({});
    expect(DEFAULT_ML_MODEL).toBe('xgb');
  });

  it('predict GET sets model param for non-default model', () => {
    service.predict(123, { model: 'rf' }).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/predict/123'));
    expect(req.request.params.get('model')).toBe('rf');
    req.flush({});
  });

  it('refreshPrediction POST to /predict/:pk/refresh', () => {
    service.refreshPrediction(123).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/predict/123/refresh'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    expect(req.request.params.has('model')).toBe(false);
    req.flush({});
  });

  it('refreshPrediction sets model param for non-default model', () => {
    service.refreshPrediction(123, { model: 'rf' }).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/predict/123/refresh'));
    expect(req.request.params.get('model')).toBe('rf');
    req.flush({});
  });

  it('listMlbTeams GET to /mlb/teams', () => {
    service.listMlbTeams().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/mlb/teams'));
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('listMlbHistory GET sets provided params', () => {
    service
      .listMlbHistory({
        season: '2024',
        team_id: 147,
        from: '2024-04-01',
        to: '2024-05-01',
        only_final: true,
        only_with_scores: true,
        limit: 10,
        offset: 5,
      })
      .subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/mlb/history/games'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('season')).toBe('2024');
    expect(req.request.params.get('team_id')).toBe('147');
    expect(req.request.params.get('from')).toBe('2024-04-01');
    expect(req.request.params.get('to')).toBe('2024-05-01');
    expect(req.request.params.get('only_final')).toBe('true');
    expect(req.request.params.get('only_with_scores')).toBe('true');
    expect(req.request.params.get('limit')).toBe('10');
    expect(req.request.params.get('offset')).toBe('5');
    req.flush([]);
  });

  it('listMlbHistory omits unset optional params', () => {
    service.listMlbHistory({ season: '2024' }).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/mlb/history/games'));
    expect(req.request.params.get('season')).toBe('2024');
    expect(req.request.params.has('team_id')).toBe(false);
    expect(req.request.params.has('only_final')).toBe(false);
    req.flush([]);
  });

  it('syncMlbRange POST forwards body', () => {
    const body = { start_date: '2024-04-01', end_date: '2024-04-07', fetch_details: true };
    service.syncMlbRange(body).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/mlb/sync-range'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({});
  });

  it('syncMlbGame POST to /mlb/games/:pk/sync with fetch_details', () => {
    service.syncMlbGame(555).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/mlb/games/555/sync'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ fetch_details: true });
    req.flush({});
  });

  it('clearAllCaches forces a fresh http hit on next listGames', () => {
    service.listGames('2024-06-01').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/games')).flush({});
    service.clearAllCaches();
    service.listGames('2024-06-01').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/games')).flush({});
  });

  it('listGames with force=true bypasses cache', () => {
    service.listGames('2024-06-01').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/games')).flush({});
    service.listGames('2024-06-01', true, { force: true }).subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/games')).flush({});
  });
});
