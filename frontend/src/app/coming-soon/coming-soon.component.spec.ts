import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, provideRouter } from '@angular/router';

import { ComingSoonComponent } from './coming-soon.component';

function configure(routeData: { title?: string; subtitle?: string }): void {
  TestBed.configureTestingModule({
    imports: [ComingSoonComponent],
    providers: [
      provideRouter([]),
      provideNoopAnimations(),
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: ActivatedRoute, useValue: { snapshot: { data: routeData } } },
    ],
  });
}

describe('ComingSoonComponent', () => {
  let fixture: ComponentFixture<ComingSoonComponent>;
  let component: ComingSoonComponent;

  it('creates with default title and subtitle when route has no data', () => {
    configure({});
    fixture = TestBed.createComponent(ComingSoonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();

    expect(component).toBeTruthy();
    expect(component.title).toBe('Próximamente');
    expect(component.subtitle).toBe('Estamos preparando esta competición.');
  });

  it('overrides title and subtitle from route snapshot data', () => {
    configure({ title: 'NBA', subtitle: 'Baloncesto en camino' });
    fixture = TestBed.createComponent(ComingSoonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();

    expect(component.title).toBe('NBA');
    expect(component.subtitle).toBe('Baloncesto en camino');
  });

  it('keeps defaults when only some route data is provided', () => {
    configure({ title: 'Soccer' });
    fixture = TestBed.createComponent(ComingSoonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();

    expect(component.title).toBe('Soccer');
    expect(component.subtitle).toBe('Estamos preparando esta competición.');
  });

  it('renders the title and subtitle in the template', () => {
    configure({ title: 'NHL', subtitle: 'Hockey pronto' });
    fixture = TestBed.createComponent(ComingSoonComponent);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('NHL');
    expect(text).toContain('Hockey pronto');
  });

  it('renders a link to MLB today', () => {
    configure({});
    fixture = TestBed.createComponent(ComingSoonComponent);
    fixture.detectChanges();

    const link: HTMLAnchorElement = fixture.nativeElement.querySelector('a[routerLink]');
    expect(link).not.toBeNull();
    expect(link.getAttribute('href')).toContain('/mlb/today');
  });
});
