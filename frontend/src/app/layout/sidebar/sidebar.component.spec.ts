import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Router, provideRouter } from '@angular/router';

import { SPORT_OPTIONS } from '../../models/sport';
import { FeaturesService } from '../../services/features.service';
import { NotificationService } from '../../services/notification.service';
import { SidebarComponent } from './sidebar.component';

describe('SidebarComponent', () => {
  let fixture: ComponentFixture<SidebarComponent>;
  let component: SidebarComponent;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        NotificationService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SidebarComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  it('creates the sidebar', () => {
    expect(component).toBeTruthy();
  });

  it('exposes the title and sport options', () => {
    expect(component.title).toBe('Sports Predictions');
    expect(component.sports()).toEqual(
      SPORT_OPTIONS.map((sport) => (sport.id === 'nba' ? { ...sport, implemented: false } : sport)),
    );
  });

  it('enables NBA when the backend feature flag is enabled', () => {
    TestBed.inject(FeaturesService).nbaEnabled.set(true);
    expect(component.sports().find((sport) => sport.id === 'nba')?.implemented).toBeTrue();
  });

  it('renders feature status and an accessible unread-notification label', () => {
    expect(fixture.nativeElement.textContent).toContain('pronto');

    TestBed.inject(NotificationService).push('Nueva alerta');
    fixture.detectChanges();

    const notificationButton = fixture.nativeElement.querySelector(
      'button[aria-label^="Notificaciones"]',
    );
    expect(notificationButton.getAttribute('aria-label')).toBe('Notificaciones, 1 sin leer');
    expect(notificationButton.querySelector('mat-icon').getAttribute('aria-hidden')).toBe('true');
  });

  it('toggles the collapsed flag', () => {
    expect(component.collapsed).toBeFalse();
    component.toggleCollapse();
    expect(component.collapsed).toBeTrue();
    component.toggleCollapse();
    expect(component.collapsed).toBeFalse();
  });

  it('maps sport ids to their route paths', () => {
    expect(component.pathFor('mlb')).toBe('/mlb');
    expect(component.pathFor('soccer')).toBe('/soccer');
    expect(component.pathFor('nba')).toBe('/nba');
  });

  it('reports the active sport row based on the current url', () => {
    spyOnProperty(router, 'url', 'get').and.returnValue('/mlb/today');
    component.ngOnInit();
    const mlb = SPORT_OPTIONS.find((s) => s.id === 'mlb')!;
    const nba = SPORT_OPTIONS.find((s) => s.id === 'nba')!;
    expect(component.sportRowActive(mlb)).toBeTrue();
    expect(component.sportRowActive(nba)).toBeFalse();
  });

  it('reports operations and bets active state', () => {
    spyOnProperty(router, 'url', 'get').and.returnValue('/operations/foo');
    component.ngOnInit();
    expect(component.linkActiveOperations()).toBeTrue();
    expect(component.linkActiveBets()).toBeFalse();
  });

  it('renders navigation links', () => {
    const links = fixture.nativeElement.querySelectorAll('a');
    expect(links.length).toBeGreaterThan(0);
  });

  it('unsubscribes cleanly on destroy', () => {
    expect(() => fixture.destroy()).not.toThrow();
  });
});
