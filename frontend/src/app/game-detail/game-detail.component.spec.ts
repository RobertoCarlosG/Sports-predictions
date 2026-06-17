import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';

import type { GameDetail, PredictionOut, TeamOut } from '../models/game';
import type { HistoryGame } from '../models/history';
import { GamesApiService } from '../services/games-api.service';
import { GameDetailComponent } from './game-detail.component';

const homeTeam: TeamOut = { id: 147, name: 'New York Yankees', abbreviation: 'NYY' };
const awayTeam: TeamOut = { id: 111, name: 'Boston Red Sox', abbreviation: 'BOS' };

function baseGame(overrides: Partial<GameDetail> = {}): GameDetail {
  return {
    game_pk: 748000,
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
    game_pk: 748000,
    home_win_probability: 0.7,
    total_runs_estimate: 8.4,
    over_under_line: 8.5,
    model_version: 'v1',
    ...overrides,
  };
}

describe('GameDetailComponent', () => {
  let fixture: ComponentFixture<GameDetailComponent>;
  let component: GameDetailComponent;
  let api: jasmine.SpyObj<GamesApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<GamesApiService>('GamesApiService', [
      'getGame',
      'predict',
      'listMlbHistory',
      'syncMlbGame',
      'refreshWeather',
      'refreshPrediction',
    ]);
    api.getGame.and.returnValue(of(baseGame()));
    api.predict.and.returnValue(of(basePrediction()));
    api.listMlbHistory.and.returnValue(of([] as HistoryGame[]));
    api.syncMlbGame.and.returnValue(of(baseGame()));
    api.refreshWeather.and.returnValue(of(baseGame()));
    api.refreshPrediction.and.returnValue(of(basePrediction()));

    await TestBed.configureTestingModule({
      imports: [GameDetailComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: GamesApiService, useValue: api },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: convertToParamMap({ gamePk: '748000' }) },
            paramMap: of(convertToParamMap({ gamePk: '748000' })),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(GameDetailComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    expect(component).toBeTruthy();
  });

  it('ngOnInit loads the game from the route param', () => {
    component.ngOnInit();
    expect(api.getGame).toHaveBeenCalledWith(748000, { force: false });
    expect(component.game?.game_pk).toBe(748000);
    expect(component.loading).toBe(false);
  });

  it('activePrediction switches with selectedModel', () => {
    component.rfPrediction = basePrediction({ model_version: 'rf' });
    component.xgbPrediction = basePrediction({ model_version: 'xgb' });
    component.selectedModel = 'xgb';
    expect(component.activePrediction?.model_version).toBe('xgb');
    component.selectModel('rf');
    expect(component.selectedModel).toBe('rf');
    expect(component.activePrediction?.model_version).toBe('rf');
  });

  it('insufficientData reflects defaults_injected on the active prediction', () => {
    component.selectedModel = 'xgb';
    component.xgbPrediction = basePrediction({ defaults_injected: true });
    expect(component.insufficientData).toBe(true);
    component.xgbPrediction = basePrediction({ defaults_injected: false });
    expect(component.insufficientData).toBe(false);
  });

  it('hasScore checks numeric scores', () => {
    expect(component.hasScore(baseGame())).toBe(false);
    expect(component.hasScore(baseGame({ home_score: 3, away_score: 2 }))).toBe(true);
  });

  it('abbr maps a known MLB team', () => {
    expect(component.abbr({ id: 147, name: 'x', abbreviation: 'HOME' })).toBe('NYY');
  });

  it('favoriteBarProbability returns favorite prob or null', () => {
    component.selectedModel = 'xgb';
    component.xgbPrediction = null;
    expect(component.favoriteBarProbability()).toBeNull();
    component.xgbPrediction = basePrediction({ home_win_probability: 0.7 });
    expect(component.favoriteBarProbability()).toBeCloseTo(0.7);
  });

  it('favoriteVictoryLabel names the favorite side', () => {
    component.game = baseGame();
    component.selectedModel = 'xgb';
    component.xgbPrediction = basePrediction({ home_win_probability: 0.7 });
    expect(component.favoriteVictoryLabel()).toBe('Victoria NYY');
  });

  it('favoriteVictoryLabel falls back without a game', () => {
    component.game = null;
    expect(component.favoriteVictoryLabel()).toBe('Victoria del favorito');
  });

  it('hasRunsProjection and formatted helpers', () => {
    component.selectedModel = 'xgb';
    component.xgbPrediction = basePrediction({ total_runs_estimate: 8.4, over_under_line: 8.5 });
    expect(component.hasRunsProjection()).toBe(true);
    expect(component.runsEstimateFormatted()).toBe('8,4');
    expect(component.ouLineFormatted()).toBe('8,5');
  });

  it('runsLeanLabel reflects over/under/push', () => {
    component.selectedModel = 'xgb';
    component.xgbPrediction = basePrediction({ total_runs_estimate: 9.0, over_under_line: 8.5 });
    expect(component.runsLeanLabel()).toBe('Sobre');
    component.xgbPrediction = basePrediction({ total_runs_estimate: 8.0, over_under_line: 8.5 });
    expect(component.runsLeanLabel()).toBe('Bajo');
    component.xgbPrediction = basePrediction({ total_runs_estimate: 8.5, over_under_line: 8.5 });
    expect(component.runsLeanLabel()).toBe('En la línea');
  });

  it('runsLeanClass exposes a single active class', () => {
    component.selectedModel = 'xgb';
    component.xgbPrediction = basePrediction({ total_runs_estimate: 9.0, over_under_line: 8.5 });
    expect(component.runsLeanClass()['detail-lean-over']).toBe(true);
  });

  it('asian handicap labels render signed lines', () => {
    component.selectedModel = 'xgb';
    component.xgbPrediction = basePrediction({
      asian_handicap: {
        home: { team_abbr: 'NYY', line: -1.5, cover_probability: 0.5 },
        away: { team_abbr: 'BOS', line: 1.5, cover_probability: 0.5 },
      },
    });
    expect(component.ahHomeLabel()).toBe('NYY -1.5 — cubrir');
    expect(component.ahAwayLabel()).toBe('BOS +1.5 — cubrir');
  });

  it('loadHeadToHead filters to the two teams', () => {
    const h2h: HistoryGame[] = [
      {
        sport_code: 'mlb',
        game_pk: 1,
        season: '2024',
        game_date: '2024-06-01',
        status: 'Final',
        home_team: homeTeam,
        away_team: awayTeam,
        home_score: 4,
        away_score: 2,
        winner_team_id: 147,
      },
      {
        sport_code: 'mlb',
        game_pk: 2,
        season: '2024',
        game_date: '2024-06-02',
        status: 'Final',
        home_team: { id: 999, name: 'Other', abbreviation: 'OTH' },
        away_team: homeTeam,
        home_score: 1,
        away_score: 0,
        winner_team_id: 999,
      },
    ];
    api.listMlbHistory.and.returnValue(of(h2h));
    (component as unknown as { loadHeadToHead(g: GameDetail): void }).loadHeadToHead(baseGame());
    expect(component.headToHead.map((r) => r.game_pk)).toEqual([1]);
  });

  it('refreshPredictionOnly updates the active model prediction', () => {
    component.ngOnInit();
    component.selectedModel = 'xgb';
    api.refreshPrediction.and.returnValue(of(basePrediction({ model_version: 'fresh' })));
    component.refreshPredictionOnly();
    expect(api.refreshPrediction).toHaveBeenCalledWith(748000, { model: 'xgb' });
    expect(component.xgbPrediction?.model_version).toBe('fresh');
    expect(component.predictionRefreshLoading).toBe(false);
    expect(component.predictionRefreshMessage).toContain('actualizada');
  });

  it('refreshData runs the full sync pipeline', () => {
    component.game = baseGame();
    component.refreshData();
    expect(api.syncMlbGame).toHaveBeenCalledWith(748000, true);
    expect(component.refreshLoading).toBe(false);
  });
});
