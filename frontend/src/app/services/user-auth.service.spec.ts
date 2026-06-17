import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { UserAuthService } from './user-auth.service';

describe('UserAuthService', () => {
  let service: UserAuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [UserAuthService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(UserAuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates', () => expect(service).toBeTruthy());

  it('starts logged out', () => {
    expect(service.isLoggedIn()).toBe(false);
  });

  it('authReady GET to /auth/ready without credentials', () => {
    service.authReady().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/auth/ready'));
    expect(req.request.method).toBe('GET');
    expect(req.request.withCredentials).toBeFalsy();
    req.flush({ login_available: true, detail: null });
  });

  it('checkSession GET sends credentials + header and sets sessionOk', () => {
    service.checkSession().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/auth/me'));
    expect(req.request.method).toBe('GET');
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.get('X-Requested-With')).toBe('XMLHttpRequest');
    req.flush({ user_id: '1', email: 'a@b.com' });
    expect(service.isLoggedIn()).toBe(true);
  });

  it('checkSession error clears sessionOk', () => {
    service.checkSession().subscribe({ error: () => undefined });
    const req = httpMock.expectOne((r) => r.url.endsWith('/auth/me'));
    req.flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(service.isLoggedIn()).toBe(false);
  });

  it('loginEmail POST sets sessionOk and posts credentials', () => {
    service.loginEmail('a@b.com', 'pw').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/auth/login'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'a@b.com', password: 'pw' });
    expect(req.request.withCredentials).toBe(true);
    req.flush({ user_id: '1', email: 'a@b.com' });
    expect(service.isLoggedIn()).toBe(true);
  });

  it('registerEmail POST sends display_name and sets sessionOk', () => {
    service.registerEmail('a@b.com', 'pw', 'Alice').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/auth/register'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'a@b.com', password: 'pw', display_name: 'Alice' });
    req.flush({ user_id: '1', email: 'a@b.com' });
    expect(service.isLoggedIn()).toBe(true);
  });

  it('registerEmail defaults display_name to null when omitted', () => {
    service.registerEmail('a@b.com', 'pw').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/auth/register'));
    expect(req.request.body).toEqual({ email: 'a@b.com', password: 'pw', display_name: null });
    req.flush({ user_id: '1', email: 'a@b.com' });
  });

  it('logout POST clears sessionOk', () => {
    service.loginEmail('a@b.com', 'pw').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/auth/login')).flush({ user_id: '1', email: 'a@b.com' });
    expect(service.isLoggedIn()).toBe(true);

    service.logout().subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/auth/logout'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({ message: 'bye', detail: 'ok' });
    expect(service.isLoggedIn()).toBe(false);
  });

  it('clearSessionLocal flips sessionOk to false', () => {
    service.loginEmail('a@b.com', 'pw').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/auth/login')).flush({ user_id: '1', email: 'a@b.com' });
    service.clearSessionLocal();
    expect(service.isLoggedIn()).toBe(false);
  });

  it('startGoogleLogin redirects to the google endpoint', () => {
    // Espiamos la indirección redirectTo para no navegar el runner de tests.
    const spy = spyOn(service as unknown as { redirectTo(url: string): void }, 'redirectTo');
    service.startGoogleLogin();
    expect(spy).toHaveBeenCalledWith(jasmine.stringMatching(/\/auth\/google$/));
  });
});
