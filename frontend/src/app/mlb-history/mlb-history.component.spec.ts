import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import type { TeamOut } from '../models/game';
import type { HistoryGame, MlbSyncRangeResult } from '../models/history';
import { GamesApiService } from '../services/games-api.service';
import { MlbHistoryComponent } from './mlb-history.component';

const homeTeam: TeamOut = { id: 147, name: 'New York Yankees', abbreviation: 'NYY' };
const awayTeam: TeamOut = { id: 111, name: 'Boston Red Sox', abbreviation: 'BOS' };

const sampleGame: HistoryGame = {
  sport_code: 'mlb',
  game_pk: 12345,
  season: '2025',
  game_date: '2025-04-10',
  status: 'Final',
  home_team: homeTeam,
  away_team: awayTeam,
  home_score: 5,
  away_score: 3,
  winner_team_id: 147,
};

const syncResult: MlbSyncRangeResult = {
  start_date: '2025-04-10',
  end_date: '2025-04-10',
  days_synced: 1,
};

describe('MlbHistoryComponent', () => {
  let fixture: ComponentFixture<MlbHistoryComponent>;
  let component: MlbHistoryComponent;
  let api: jasmine.SpyObj<GamesApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<GamesApiService>('GamesApiService', [
      'listMlbHistory',
      'listMlbTeams',
      'syncMlbRange',
    ]);
    api.listMlbHistory.and.returnValue(of([sampleGame]));
    api.listMlbTeams.and.returnValue(of([homeTeam, awayTeam]));
    api.syncMlbRange.and.returnValue(of(syncResult));

    await TestBed.configureTestingModule({
      imports: [MlbHistoryComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: GamesApiService, useValue: api },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(MlbHistoryComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('creates the component', () => {
    expect(component).toBeTruthy();
  });

  it('loads history and teams on init', () => {
    expect(api.listMlbHistory).toHaveBeenCalled();
    expect(api.listMlbTeams).toHaveBeenCalled();
    expect(component.games).toEqual([sampleGame]);
    expect(component.teams).toEqual([homeTeam, awayTeam]);
    expect(component.loading).toBeFalse();
    expect(component.loadError).toBeFalse();
  });

  it('builds the season year choices', () => {
    expect(component.seasonYearChoices.length).toBeGreaterThan(0);
    expect(component.seasonYearChoices.every((y) => y >= 2020)).toBeTrue();
  });

  it('sets a 7-day window for the last7 quick range', () => {
    component.applyQuick('last7', false);
    expect(component.quickActive).toBe('last7');
    expect(component.dateFrom).toBeTruthy();
    expect(component.dateTo).toBe(component.seasonBounds.today);
    expect(component.dateFrom < component.dateTo).toBeTrue();
  });

  it('sets the full season window for the season quick range', () => {
    component.applyQuick('season', false);
    expect(component.quickActive).toBe('season');
    expect(component.dateFrom).toBe(component.seasonBounds.min);
    expect(component.dateTo).toBe(component.seasonBounds.today);
  });

  it('forces a reload bypassing the cache', () => {
    api.listMlbHistory.calls.reset();
    component.forceReload();
    expect(api.listMlbHistory).toHaveBeenCalledWith(
      jasmine.anything(),
      { force: true },
    );
  });

  it('flags load errors when the history request fails', () => {
    api.listMlbHistory.and.returnValue(
      new (class {
        subscribe(handlers: { error: () => void }) {
          handlers.error();
          return { unsubscribe() {} };
        }
      })() as never,
    );
    component.load();
    expect(component.loadError).toBeTrue();
    expect(component.loading).toBeFalse();
  });

  it('rejects sync ranges without both dates', () => {
    component.syncStart = '';
    component.syncEnd = '';
    component.runSyncRange();
    expect(component.syncBanner).toBe('Elige fechas de inicio y fin.');
    expect(api.syncMlbRange).not.toHaveBeenCalled();
  });

  it('syncs each day in a valid range', () => {
    const { min } = component.seasonBounds;
    component.syncStart = min;
    component.syncEnd = min;
    component.runSyncRange();
    expect(api.syncMlbRange).toHaveBeenCalled();
    expect(component.syncLoading).toBeFalse();
    expect(component.syncBanner).toContain('Listo');
  });

  it('stringifies year values', () => {
    expect(component.yearStr(2025)).toBe('2025');
  });
});
