import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import type { GameDetail, GamesListResponse, PredictionOut, TeamOut } from '../models/game';
import { GamesApiService } from '../services/games-api.service';
import { GameListComponent } from './game-list.component';

const homeTeam: TeamOut = { id: 147, name: 'New York Yankees', abbreviation: 'NYY' };
const awayTeam: TeamOut = { id: 111, name: 'Boston Red Sox', abbreviation: 'BOS' };

function baseGame(overrides: Partial<GameDetail> = {}): GameDetail {
  return {
    game_pk: 12345,
    season: '2024',
    game_date: '2024-07-04',
    status: 'Scheduled',
    home_team: homeTeam,
    away_team: awayTeam,
    home_score: null,
    away_score: null,
    venue_id: 1,
    venue_name: 'Yankee Stadium',
    lineups: null,
    boxscore: null,
    weather: null,
    prediction: null,
    ...overrides,
  };
}

function basePrediction(overrides: Partial<PredictionOut> = {}): PredictionOut {
  return {
    game_pk: 12345,
    home_win_probability: 0.7,
    total_runs_estimate: 8.4,
    over_under_line: 8.5,
    model_version: 'v1',
    ...overrides,
  };
}

function listResponse(games: GameDetail[]): GamesListResponse {
  return { games, meta: { warnings: [], info: [], missing_snapshot_count: 0 } };
}

describe('GameListComponent', () => {
  let fixture: ComponentFixture<GameListComponent>;
  let component: GameListComponent;
  let api: jasmine.SpyObj<GamesApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<GamesApiService>('GamesApiService', ['listGames', 'predict']);
    api.listGames.and.returnValue(of(listResponse([])));
    api.predict.and.returnValue(of(basePrediction()));

    await TestBed.configureTestingModule({
      imports: [GameListComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: GamesApiService, useValue: api },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(GameListComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    expect(component).toBeTruthy();
  });

  it('gamesForDate groups games by iso date via the computed map', () => {
    component.games.set([
      baseGame({ game_pk: 1, game_date: '2024-07-04' }),
      baseGame({ game_pk: 2, game_date: '2024-07-04' }),
      baseGame({ game_pk: 3, game_date: '2024-07-05' }),
    ]);
    expect(component.gamesForDate('2024-07-04').map((g) => g.game_pk)).toEqual([1, 2]);
    expect(component.gamesForDate('2024-07-05').map((g) => g.game_pk)).toEqual([3]);
    expect(component.gamesForDate('2024-12-25')).toEqual([]);
  });

  it('dayKeys returns sorted unique dates', () => {
    component.games.set([
      baseGame({ game_pk: 1, game_date: '2024-07-05' }),
      baseGame({ game_pk: 2, game_date: '2024-07-04' }),
      baseGame({ game_pk: 3, game_date: '2024-07-04' }),
    ]);
    expect(component.dayKeys()).toEqual(['2024-07-04', '2024-07-05']);
  });

  it('probFor reads the homeWinByPk map', () => {
    const g = baseGame({ game_pk: 99 });
    component.homeWinByPk.set({ 99: 0.62 });
    expect(component.probFor(g)).toBeCloseTo(0.62);
  });

  it('probFor returns undefined while predictions load and value missing', () => {
    const g = baseGame({ game_pk: 77 });
    component.homeWinByPk.set({});
    component.predictionsLoading.set(true);
    expect(component.probFor(g)).toBeUndefined();
  });

  it('probFor returns null when value is missing and not loading', () => {
    const g = baseGame({ game_pk: 55 });
    component.homeWinByPk.set({});
    component.predictionsLoading.set(false);
    expect(component.probFor(g)).toBeNull();
  });

  it('onDateSelection loads games and applies headlines for tomorrow', () => {
    component.onDateSelection({ preset: 'tomorrow', dates: ['2024-07-05'] });
    expect(api.listGames).toHaveBeenCalledWith('2024-07-05', true, { force: false });
    expect(component.pageTitle()).toBe('Mañana en MLB');
    expect(component.dateSummary()).toBe('2024-07-05');
  });

  it('onDateSelection with predictions in payload populates homeWinByPk', () => {
    api.listGames.and.returnValue(
      of(listResponse([baseGame({ game_pk: 12345, prediction: basePrediction() })])),
    );
    component.onDateSelection({ preset: 'today', dates: ['2024-07-04'] });
    expect(component.games().length).toBe(1);
    expect(component.homeWinByPk()[12345]).toBeCloseTo(0.7);
    expect(component.loading()).toBe(false);
  });

  it('onDateSelection with week preset summarises a range', () => {
    component.onDateSelection({
      preset: 'week',
      dates: ['2024-07-01', '2024-07-02', '2024-07-07'],
    });
    expect(component.pageTitle()).toBe('Esta semana en MLB');
    expect(component.dateSummary()).toBe('2024-07-01 — 2024-07-07');
  });

  it('empty date selection clears the lists', () => {
    component.games.set([baseGame()]);
    component.onDateSelection({ preset: 'today', dates: [] });
    expect(component.games()).toEqual([]);
    expect(component.listMeta()).toBeNull();
  });

  it('retry forces a reload of the last selection', () => {
    component.onDateSelection({ preset: 'today', dates: ['2024-07-04'] });
    api.listGames.calls.reset();
    component.loadError.set(true);
    component.retry();
    expect(api.listGames).toHaveBeenCalledWith('2024-07-04', true, { force: true });
    expect(component.loadError()).toBe(false);
  });
});
