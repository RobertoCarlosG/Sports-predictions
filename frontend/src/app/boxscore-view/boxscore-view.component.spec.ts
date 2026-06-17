import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { BoxscoreViewComponent } from './boxscore-view.component';

/** Realistic statsapi.mlb.com-style boxscore payload. */
function statsapiBoxscore(): Record<string, unknown> {
  return {
    teams: {
      away: {
        team: { abbreviation: 'BOS', teamName: 'Red Sox', name: 'Boston Red Sox' },
        teamStats: {
          batting: { runs: 4, hits: 9, errors: 1 },
          fielding: { errors: 2 },
        },
        innings: [{ runs: 1 }, { runs: 0 }, { runs: 3 }],
      },
      home: {
        team: { abbreviation: 'NYY', teamName: 'Yankees', name: 'New York Yankees' },
        teamStats: {
          batting: { runs: 5, hits: 11, errors: 0 },
          fielding: { errors: 0 },
        },
        innings: [{ r: 2 }, { r: 0 }, { r: 3 }],
      },
    },
  };
}

describe('BoxscoreViewComponent', () => {
  let fixture: ComponentFixture<BoxscoreViewComponent>;
  let component: BoxscoreViewComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BoxscoreViewComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(BoxscoreViewComponent);
    component = fixture.componentInstance;
  });

  it('creates with a null boxscore input', () => {
    fixture.componentRef.setInput('boxscore', null);
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('summary is null when boxscore is null', () => {
    fixture.componentRef.setInput('boxscore', null);
    expect(component.summary).toBeNull();
  });

  it('summary is null when boxscore has no teams', () => {
    fixture.componentRef.setInput('boxscore', { foo: 'bar' });
    expect(component.summary).toBeNull();
  });

  it('summary parses R/H/E for both sides from a statsapi payload', () => {
    fixture.componentRef.setInput('boxscore', statsapiBoxscore());
    const summary = component.summary;
    expect(summary).not.toBeNull();
    expect(summary?.away?.label).toBe('BOS');
    expect(summary?.away?.runs).toBe(4);
    expect(summary?.away?.hits).toBe(9);
    // fielding errors take precedence over batting errors
    expect(summary?.away?.errors).toBe(2);
    expect(summary?.home?.label).toBe('NYY');
    expect(summary?.home?.runs).toBe(5);
    expect(summary?.home?.errors).toBe(0);
  });

  it('summary builds the inning-by-inning line (supports runs and r keys)', () => {
    fixture.componentRef.setInput('boxscore', statsapiBoxscore());
    const innings = component.summary?.innings ?? [];
    expect(innings.length).toBe(3);
    expect(innings[0]).toEqual({ inning: 1, awayRuns: 1, homeRuns: 2 });
    expect(innings[2]).toEqual({ inning: 3, awayRuns: 3, homeRuns: 3 });
  });

  it('cell() renders a dash for null/undefined and the value otherwise', () => {
    expect(component.cell(null)).toBe('—');
    expect(component.cell(undefined as unknown as number | null)).toBe('—');
    expect(component.cell(0)).toBe('0');
    expect(component.cell(7)).toBe('7');
  });

  it('renders summary content when a boxscore is provided', () => {
    fixture.componentRef.setInput('boxscore', statsapiBoxscore());
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('BOS');
    expect(fixture.nativeElement.textContent).toContain('NYY');
  });
});
