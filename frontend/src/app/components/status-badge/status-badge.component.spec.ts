import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { StatusBadgeComponent } from './status-badge.component';

describe('StatusBadgeComponent', () => {
  let fixture: ComponentFixture<StatusBadgeComponent>;
  let component: StatusBadgeComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StatusBadgeComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(StatusBadgeComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('resolves kind from the API status text', () => {
    component.apiStatus = 'In Progress';
    expect(component.resolvedKind).toBe('live');
    expect(component.label).toBe('En vivo');

    component.apiStatus = 'Final';
    expect(component.resolvedKind).toBe('final');
    expect(component.label).toBe('Final');

    component.apiStatus = 'Scheduled';
    expect(component.resolvedKind).toBe('upcoming');
    expect(component.label).toBe('Próximo');
  });

  it('prefers the explicit kind input over the API status', () => {
    component.apiStatus = 'Final';
    component.kind = 'live';
    expect(component.resolvedKind).toBe('live');
    expect(component.label).toBe('En vivo');
  });

  it('renders the live label and class', () => {
    component.apiStatus = 'Live';
    fixture.detectChanges();
    const badge = fixture.nativeElement.querySelector('.badge');
    expect(badge.textContent).toContain('En vivo');
    expect(badge.classList).toContain('badge-live');
  });

  it('renders the final label and class', () => {
    component.apiStatus = 'Game Over';
    fixture.detectChanges();
    const badge = fixture.nativeElement.querySelector('.badge');
    expect(badge.textContent).toContain('Final');
    expect(badge.classList).toContain('badge-final');
  });

  it('renders the upcoming label and class by default', () => {
    fixture.detectChanges();
    const badge = fixture.nativeElement.querySelector('.badge');
    expect(badge.textContent).toContain('Próximo');
    expect(badge.classList).toContain('badge-upcoming');
  });
});
