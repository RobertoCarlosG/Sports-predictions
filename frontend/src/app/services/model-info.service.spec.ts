import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed, discardPeriodicTasks, fakeAsync, tick } from '@angular/core/testing';

import { ModelInfoService } from './model-info.service';

describe('ModelInfoService', () => {
  let service: ModelInfoService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ModelInfoService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ModelInfoService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('creates', () => expect(service).toBeTruthy());

  it('initial state: null info, shortLabel says not loaded, not synthetic', () => {
    expect(service.info()).toBeNull();
    expect(service.shortLabel()).toBe('Modelo no cargado');
    expect(service.isSynthetic()).toBe(false);
  });

  it('start() polls GET /model/info and sets info signal', fakeAsync(() => {
    service.start();
    tick(); // dispara la primera emisión de timer(0, …)
    const req = httpMock.expectOne((r) => r.url.endsWith('/model/info'));
    expect(req.request.method).toBe('GET');
    req.flush({ model_loaded: true, base_version: 'xgb-db-v1', is_synthetic: false });

    expect(service.info()).toEqual(
      jasmine.objectContaining({ model_loaded: true, base_version: 'xgb-db-v1' }),
    );
    expect(service.shortLabel()).toBe('xgb-db-v1');
    expect(service.isSynthetic()).toBe(false);

    // Stop the interval timer so verify()/fakeAsync don't complain about pending tasks.
    drainPolling(httpMock);
  }));

  it('shortLabel falls back to rf-v0 when loaded without base_version', fakeAsync(() => {
    service.start();
    tick(); // dispara la primera emisión de timer(0, …)
    const req = httpMock.expectOne((r) => r.url.endsWith('/model/info'));
    req.flush({ model_loaded: true });
    expect(service.shortLabel()).toBe('rf-v0');
    drainPolling(httpMock);
  }));

  it('isSynthetic true when payload flags synthetic', fakeAsync(() => {
    service.start();
    tick(); // dispara la primera emisión de timer(0, …)
    httpMock
      .expectOne((r) => r.url.endsWith('/model/info'))
      .flush({ model_loaded: true, is_synthetic: true });
    expect(service.isSynthetic()).toBe(true);
    drainPolling(httpMock);
  }));

  it('poll http error leaves info null (catchError -> null)', fakeAsync(() => {
    service.start();
    tick(); // dispara la primera emisión de timer(0, …)
    const req = httpMock.expectOne((r) => r.url.endsWith('/model/info'));
    req.flush({}, { status: 500, statusText: 'err' });
    expect(service.info()).toBeNull();
    drainPolling(httpMock);
  }));

  it('refreshOnce() fetches once and sets info', () => {
    service.refreshOnce();
    const req = httpMock.expectOne((r) => r.url.endsWith('/model/info'));
    expect(req.request.method).toBe('GET');
    req.flush({ model_loaded: true, base_version: 'rf-db-v2' });
    expect(service.shortLabel()).toBe('rf-db-v2');
    httpMock.verify();
  });

  it('refreshOnce() swallows errors and keeps info null', () => {
    service.refreshOnce();
    const req = httpMock.expectOne((r) => r.url.endsWith('/model/info'));
    req.flush({}, { status: 503, statusText: 'down' });
    expect(service.info()).toBeNull();
    httpMock.verify();
  });
});

/**
 * The polling Observable uses timer(0, 5min) inside shareReplay. After flushing
 * the first emission we verify no extra HTTP went out, then discard the pending
 * periodic timer so fakeAsync doesn't report "pending timers in the queue".
 */
function drainPolling(httpMock: HttpTestingController): void {
  httpMock.verify();
  discardPeriodicTasks();
}
