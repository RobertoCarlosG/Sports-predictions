import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import {
  UserAuthService,
  type UserAuthReadyResponse,
  type UserSessionResponse,
} from '../services/user-auth.service';
import { LoginPageComponent } from './login-page.component';

function session(): UserSessionResponse {
  return { user_id: 'u1', email: 'user@example.com', display_name: 'User' };
}

function authReady(overrides: Partial<UserAuthReadyResponse> = {}): UserAuthReadyResponse {
  return {
    login_available: true,
    detail: null,
    google_configured: true,
    email_login_available: true,
    ...overrides,
  };
}

describe('LoginPageComponent', () => {
  let fixture: ComponentFixture<LoginPageComponent>;
  let component: LoginPageComponent;
  let auth: jasmine.SpyObj<UserAuthService>;
  let router: Router;

  beforeEach(async () => {
    auth = jasmine.createSpyObj<UserAuthService>('UserAuthService', [
      'isLoggedIn',
      'checkSession',
      'authReady',
      'loginEmail',
      'registerEmail',
      'startGoogleLogin',
    ]);
    auth.isLoggedIn.and.returnValue(false);
    // Default: no active session -> falls through to authReady config load.
    auth.checkSession.and.returnValue(throwError(() => new Error('no session')));
    auth.authReady.and.returnValue(of(authReady()));
    auth.loginEmail.and.returnValue(of(session()));
    auth.registerEmail.and.returnValue(of(session()));

    await TestBed.configureTestingModule({
      imports: [LoginPageComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: UserAuthService, useValue: auth },
      ],
    }).compileComponents();
    // Router real (RouterLink lo necesita); solo espiamos navigate.
    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);
    fixture = TestBed.createComponent(LoginPageComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('redirects immediately when already logged in', () => {
    auth.isLoggedIn.and.returnValue(true);
    fixture.detectChanges();
    expect(router.navigate).toHaveBeenCalledWith(['/bets']);
    expect(auth.checkSession).not.toHaveBeenCalled();
  });

  it('redirects when checkSession succeeds', () => {
    auth.checkSession.and.returnValue(of(session()));
    fixture.detectChanges();
    expect(router.navigate).toHaveBeenCalledWith(['/bets']);
  });

  it('loads auth config and stops the spinner when there is no session', () => {
    fixture.detectChanges();
    expect(component.checkingSession()).toBe(false);
    expect(auth.authReady).toHaveBeenCalled();
    expect(component.googleAvailable).toBe(true);
    expect(component.emailAvailable).toBe(true);
  });

  it('falls back to login_available=false config when authReady errors', () => {
    auth.authReady.and.returnValue(throwError(() => new Error('boom')));
    fixture.detectChanges();
    expect(component.authConfig()?.login_available).toBe(false);
    expect(component.googleAvailable).toBe(false);
  });

  it('toggleMode flips mode and clears password/error', () => {
    component.password = 'secret';
    component.error.set('algo');
    component.toggleMode();
    expect(component.mode()).toBe('register');
    expect(component.password).toBe('');
    expect(component.error()).toBeNull();
    component.toggleMode();
    expect(component.mode()).toBe('login');
  });

  it('submitEmail validates required fields', () => {
    component.email = '   ';
    component.password = '';
    component.submitEmail();
    expect(component.error()).toBe('Completa todos los campos.');
    expect(auth.loginEmail).not.toHaveBeenCalled();
  });

  it('submitEmail calls loginEmail in login mode and navigates on success', () => {
    component.email = '  user@example.com  ';
    component.password = 'pw';
    component.submitEmail();
    expect(auth.loginEmail).toHaveBeenCalledWith('user@example.com', 'pw');
    expect(router.navigate).toHaveBeenCalledWith(['/bets']);
  });

  it('submitEmail calls registerEmail in register mode with trimmed display name', () => {
    component.mode.set('register');
    component.email = 'new@example.com';
    component.password = 'pw';
    component.displayName = '  Roberto  ';
    component.submitEmail();
    expect(auth.registerEmail).toHaveBeenCalledWith('new@example.com', 'pw', 'Roberto');
  });

  it('submitEmail surfaces a server detail message on error', () => {
    auth.loginEmail.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 400,
            error: { detail: 'Cuenta bloqueada' },
          }),
      ),
    );
    component.email = 'user@example.com';
    component.password = 'pw';
    component.submitEmail();
    expect(component.loading()).toBe(false);
    expect(component.error()).toBe('Cuenta bloqueada');
  });

  it('submitEmail maps 401 to a friendly message', () => {
    auth.loginEmail.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 401, error: null })),
    );
    component.email = 'user@example.com';
    component.password = 'bad';
    component.submitEmail();
    expect(component.error()).toBe('Email o contraseña incorrectos.');
  });

  it('submitEmail maps 409 in register mode', () => {
    component.mode.set('register');
    auth.registerEmail.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 409, error: null })),
    );
    component.email = 'dupe@example.com';
    component.password = 'pw';
    component.submitEmail();
    expect(component.error()).toBe('Ya existe una cuenta con ese email.');
  });

  it('submitEmail uses a generic message for non-HTTP errors', () => {
    auth.loginEmail.and.returnValue(throwError(() => new Error('network down')));
    component.email = 'user@example.com';
    component.password = 'pw';
    component.submitEmail();
    expect(component.error()).toBe('Ocurrió un error. Inténtalo de nuevo.');
  });

  it('loginGoogle delegates to the auth service', () => {
    component.loginGoogle();
    expect(auth.startGoogleLogin).toHaveBeenCalled();
  });
});
