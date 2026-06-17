import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { SportTabNavComponent } from './sport-tab-nav.component';

describe('SportTabNavComponent', () => {
  let fixture: ComponentFixture<SportTabNavComponent>;
  let component: SportTabNavComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SportTabNavComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(SportTabNavComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('pathFor returns the correct route per sport', () => {
    expect(component.pathFor('mlb')).toBe('/mlb/today');
    expect(component.pathFor('soccer')).toBe('/soccer');
    expect(component.pathFor('nba')).toBe('/nba');
  });

  it('renders a tab per sport option', () => {
    fixture.detectChanges();
    const tabs = fixture.nativeElement.querySelectorAll('a.tab');
    expect(tabs.length).toBe(component.sports.length);
  });

  it('marks the active sport tab', () => {
    component.active = 'mlb';
    fixture.detectChanges();
    const active = fixture.nativeElement.querySelector('a.tab-active');
    expect(active?.textContent).toContain('MLB');
  });

  it('shows a "pronto" marker on unimplemented sports', () => {
    fixture.detectChanges();
    const soon = fixture.nativeElement.querySelectorAll('.soon');
    expect(soon.length).toBeGreaterThan(0);
  });

  it('highlights nothing when active is null', () => {
    component.active = null;
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a.tab-active')).toBeNull();
  });
});
