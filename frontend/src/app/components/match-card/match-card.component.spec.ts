import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import type { GameDetail, PredictionOut, TeamOut } from '../../models/game';
import { MatchCardComponent } from './match-card.component';

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

describe('MatchCardComponent', () => {
  let fixture: ComponentFixture<MatchCardComponent>;
  let component: MatchCardComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MatchCardComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(MatchCardComponent);
    component = fixture.componentInstance;
  });

  it('creates with a required game input', () => {
    fixture.componentRef.setInput('game', baseGame());
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('renders team abbreviations and date', () => {
    fixture.componentRef.setInput('game', baseGame());
    fixture.detectChanges();
    const teams = fixture.nativeElement.querySelectorAll('.team');
    expect(teams[0].textContent).toContain('BOS');
    expect(teams[1].textContent).toContain('NYY');
    expect(fixture.nativeElement.querySelector('.meta')?.textContent).toContain('2024-07-04');
  });

  it('abbr() maps a known MLB team id', () => {
    expect(component.abbr({ id: 147, name: 'x', abbreviation: 'HOME' })).toBe('NYY');
  });

  it('hasScore() reflects numeric scores', () => {
    fixture.componentRef.setInput('game', baseGame());
    expect(component.hasScore()).toBe(false);
    fixture.componentRef.setInput('game', baseGame({ home_score: 3, away_score: 2 }));
    expect(component.hasScore()).toBe(true);
  });

  it('renders score when present', () => {
    fixture.componentRef.setInput('game', baseGame({ home_score: 3, away_score: 2 }));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.score')?.textContent).toContain('2');
    expect(fixture.nativeElement.querySelector('.score')?.textContent).toContain('3');
  });

  it('favoriteBarProbability returns undefined when prob undefined', () => {
    fixture.componentRef.setInput('game', baseGame());
    expect(component.favoriteBarProbability).toBeUndefined();
  });

  it('favoriteBarProbability returns the home prob when home is favorite', () => {
    fixture.componentRef.setInput('game', baseGame());
    fixture.componentRef.setInput('homeWinProbability', 0.7);
    expect(component.favoriteBarProbability).toBeCloseTo(0.7);
  });

  it('favoriteBarProbability flips when away is favorite', () => {
    fixture.componentRef.setInput('game', baseGame());
    fixture.componentRef.setInput('homeWinProbability', 0.3);
    expect(component.favoriteBarProbability).toBeCloseTo(0.7);
  });

  it('favoriteVictoryLabel names the favorite team', () => {
    fixture.componentRef.setInput('game', baseGame());
    fixture.componentRef.setInput('homeWinProbability', 0.7);
    expect(component.favoriteVictoryLabel).toBe('Victoria NYY');
  });

  it('favoriteVictoryLabel falls back when probability is undefined', () => {
    fixture.componentRef.setInput('game', baseGame());
    expect(component.favoriteVictoryLabel).toBe('Victoria del favorito');
  });

  it('hasPrediction and insufficientData reflect prediction', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({ prediction: basePrediction({ defaults_injected: true }) }),
    );
    expect(component.hasPrediction).toBe(true);
    expect(component.insufficientData).toBe(true);
  });

  it('showEvaluatedPick requires a winner pick and is_correct', () => {
    fixture.componentRef.setInput('game', baseGame({ prediction: basePrediction() }));
    expect(component.showEvaluatedPick).toBe(false);

    fixture.componentRef.setInput(
      'game',
      baseGame({
        prediction: basePrediction({ predicted_winner: 'home', is_correct: true }),
      }),
    );
    expect(component.showEvaluatedPick).toBe(true);
    expect(component.predictionCorrect).toBe(true);
    expect(component.predictionIncorrect).toBe(false);
  });

  it('predictedWinnerLabel and actualWinnerLabel resolve team names', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({
        prediction: basePrediction({
          predicted_winner: 'away',
          actual_winner: 'home',
          is_correct: false,
        }),
      }),
    );
    expect(component.predictedWinnerLabel).toBe('Victoria BOS');
    expect(component.actualWinnerLabel).toBe('Ganó NYY');
  });

  it('actualWinnerLabel handles tie', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({
        prediction: basePrediction({ predicted_winner: 'home', actual_winner: 'tie', is_correct: false }),
      }),
    );
    expect(component.actualWinnerLabel).toBe('Empate');
  });

  it('confidencePercent computes percentage for the picked side', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({
        prediction: basePrediction({
          home_win_probability: 0.7,
          predicted_winner: 'home',
          is_correct: true,
        }),
      }),
    );
    expect(component.confidencePercent).toBe('70% a favor de NYY');
  });

  it('confidencePercent uses complement for away pick', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({
        prediction: basePrediction({
          home_win_probability: 0.3,
          predicted_winner: 'away',
          is_correct: true,
        }),
      }),
    );
    expect(component.confidencePercent).toBe('70% a favor de BOS');
  });

  it('hasRunsLine detects valid runs/line', () => {
    fixture.componentRef.setInput('game', baseGame({ prediction: basePrediction() }));
    expect(component.hasRunsLine).toBe(true);
  });

  it('runsOuTendency returns over/under/push around the line', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({ prediction: basePrediction({ total_runs_estimate: 9.0, over_under_line: 8.5 }) }),
    );
    expect(component.runsOuTendency).toBe('over');
    expect(component.runsOuTendencyLabel).toBe('Sobre');

    fixture.componentRef.setInput(
      'game',
      baseGame({ prediction: basePrediction({ total_runs_estimate: 8.0, over_under_line: 8.5 }) }),
    );
    expect(component.runsOuTendency).toBe('under');
    expect(component.runsOuTendencyLabel).toBe('Bajo');

    fixture.componentRef.setInput(
      'game',
      baseGame({ prediction: basePrediction({ total_runs_estimate: 8.5, over_under_line: 8.5 }) }),
    );
    expect(component.runsOuTendency).toBe('push');
    expect(component.runsOuTendencyLabel).toBe('En la línea');
  });

  it('formatRunNumber uses comma decimals', () => {
    expect(component.formatRunNumber(8.5)).toBe('8,5');
  });

  it('runsEstimateDisplay and ouLineDisplay format the numbers', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({ prediction: basePrediction({ total_runs_estimate: 8.4, over_under_line: 8.5 }) }),
    );
    expect(component.runsEstimateDisplay).toBe('8,4');
    expect(component.ouLineDisplay).toBe('8,5');
  });

  it('renders the evaluated-pick block when applicable', () => {
    fixture.componentRef.setInput(
      'game',
      baseGame({
        prediction: basePrediction({ predicted_winner: 'home', is_correct: true }),
      }),
    );
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.prediction-evaluation')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('.prediction-badge.correct')).toBeTruthy();
  });
});
