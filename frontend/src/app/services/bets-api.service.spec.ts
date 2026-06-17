import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { BetsApiService } from './bets-api.service';

describe('BetsApiService', () => {
  let service: BetsApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [BetsApiService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(BetsApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates', () => expect(service).toBeTruthy());

  it('listBanks GET with credentials + header', () => {
    service.listBanks().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/banks'));
    expect(req.request.method).toBe('GET');
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.get('X-Requested-With')).toBe('XMLHttpRequest');
    req.flush([]);
  });

  it('createBank POST forwards body', () => {
    const body = { name: 'Main', initial_amount: 1000, currency: 'USD' };
    service.createBank(body).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/banks'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({});
  });

  it('updateBank PUT to /banks/:id', () => {
    service.updateBank(7, { name: 'New', is_active: false }).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/banks/7'));
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({ name: 'New', is_active: false });
    req.flush({});
  });

  it('listPeriods GET sets only provided params', () => {
    service.listPeriods(3, 2024).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/periods'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('bank_id')).toBe('3');
    expect(req.request.params.get('year')).toBe('2024');
    req.flush([]);
  });

  it('listPeriods GET omits params when undefined', () => {
    service.listPeriods().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/periods'));
    expect(req.request.params.has('bank_id')).toBe(false);
    expect(req.request.params.has('year')).toBe(false);
    req.flush([]);
  });

  it('createPeriod POST', () => {
    const body = { bank_id: 1, year: 2024, month: 6 };
    service.createPeriod(body).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/periods'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({});
  });

  it('closePeriod POST to /periods/:id/close', () => {
    service.closePeriod(5).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/periods/5/close'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({});
  });

  it('periodStats GET to /periods/:id/stats', () => {
    service.periodStats(9).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/periods/9/stats'));
    expect(req.request.method).toBe('GET');
    req.flush({});
  });

  it('exportPeriod GET returns blob', () => {
    service.exportPeriod(2).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/periods/2/export'));
    expect(req.request.method).toBe('GET');
    expect(req.request.responseType).toBe('blob');
    req.flush(new Blob(['x']));
  });

  it('listBets GET sets only provided params', () => {
    service.listBets({ bank_id: 1, status: 'pending' }).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('bank_id')).toBe('1');
    expect(req.request.params.get('status')).toBe('pending');
    expect(req.request.params.has('period_id')).toBe(false);
    expect(req.request.params.has('game_pk')).toBe(false);
    req.flush([]);
  });

  it('createBet POST forwards body', () => {
    const body = {
      bank_id: 1,
      game_pk: 12345,
      bet_type: 'moneyline' as const,
      bet_side: 'home' as const,
      stake: 50,
      odds: 1.9,
    };
    service.createBet(body).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({});
  });

  it('globalStats GET sets bank_id param when given', () => {
    service.globalStats(4).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/stats'));
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('bank_id')).toBe('4');
    req.flush({});
  });

  it('resolveBet POST to /:id/resolve', () => {
    service.resolveBet(11).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/bets/11/resolve'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({});
  });
});
