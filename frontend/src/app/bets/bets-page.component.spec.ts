import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatSnackBar } from '@angular/material/snack-bar';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import type { GameDetail, GamesListResponse, TeamOut } from '../models/game';
import {
  BetBankOut,
  BetOut,
  BetPeriodOut,
  BetPeriodStatsOut,
  BetsApiService,
  BetsStatsOut,
} from '../services/bets-api.service';
import { GamesApiService } from '../services/games-api.service';
import { UserAuthService, type UserSessionResponse } from '../services/user-auth.service';
import { BetsPageComponent } from './bets-page.component';

const homeTeam: TeamOut = {
  id: 147,
  name: 'New York Yankees',
  abbreviation: 'NYY',
  league: 'AL',
  division: 'AL East',
};
const awayTeam: TeamOut = {
  id: 111,
  name: 'Boston Red Sox',
  abbreviation: 'BOS',
  league: 'AL',
  division: 'AL East',
};

function game(overrides: Partial<GameDetail> = {}): GameDetail {
  return {
    game_pk: 777,
    season: '2026',
    game_date: '2026-06-16',
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
    prediction: {
      game_pk: 777,
      home_win_probability: 0.62,
      total_runs_estimate: 9.1,
      over_under_line: 8.5,
      model_version: 'v1',
    },
    ...overrides,
  };
}

function gamesResponse(games: GameDetail[]): GamesListResponse {
  return { games, meta: { warnings: [], info: [], missing_snapshot_count: 0 } };
}

function bank(): BetBankOut {
  return {
    id: 1,
    name: 'Principal',
    initial_amount: 1000,
    currency: 'EUR',
    is_active: true,
    created_at: '2026-01-01',
  };
}

function period(): BetPeriodOut {
  return {
    id: 10,
    bank_id: 1,
    name: 'Junio',
    year: 2026,
    month: 6,
    starting_balance: 1000,
    closing_balance: null,
    status: 'open',
    closed_at: null,
    created_at: '2026-06-01',
  };
}

function bet(overrides: Partial<BetOut> = {}): BetOut {
  return {
    id: 100,
    bank_id: 1,
    period_id: 10,
    game_pk: 777,
    bet_type: 'moneyline',
    bet_side: 'home',
    stake: 50,
    odds: 1.9,
    ou_line: null,
    status: 'pending',
    result_source: null,
    result_checked_at: null,
    notes: null,
    created_at: '2026-06-16',
    realized_profit: null,
    ...overrides,
  };
}

function periodStats(): BetPeriodStatsOut {
  return {
    period_id: 10,
    name: 'Junio',
    starting_balance: 1000,
    closing_balance: null,
    status: 'open',
    total_stake: 100,
    realized_pnl: 20,
    roi_pct: 20,
    decided_bets: 2,
    wins: 1,
    losses: 1,
    pushes: 0,
    pending: 0,
    win_rate_ml_pct: 50,
    win_rate_ou_pct: null,
  };
}

function globalStats(overrides: Partial<BetsStatsOut> = {}): BetsStatsOut {
  return {
    total_stake: 100,
    realized_pnl: 20,
    roi_pct: 20,
    decided_bets: 2,
    wins: 1,
    losses: 1,
    pushes: 0,
    pending: 0,
    by_type: {},
    ...overrides,
  };
}

function session(): UserSessionResponse {
  return { user_id: 'u1', email: 'user@example.com', display_name: 'User' };
}

describe('BetsPageComponent', () => {
  let fixture: ComponentFixture<BetsPageComponent>;
  let component: BetsPageComponent;
  let userAuth: jasmine.SpyObj<UserAuthService>;
  let betsApi: jasmine.SpyObj<BetsApiService>;
  let gamesApi: jasmine.SpyObj<GamesApiService>;
  let snack: MatSnackBar;

  beforeEach(async () => {
    userAuth = jasmine.createSpyObj<UserAuthService>('UserAuthService', [
      'authReady',
      'checkSession',
      'startGoogleLogin',
      'logout',
      'clearSessionLocal',
    ]);
    userAuth.authReady.and.returnValue(of({ login_available: true, detail: null }));
    userAuth.checkSession.and.returnValue(of(session()));
    userAuth.logout.and.returnValue(of({ message: 'ok', detail: 'bye' }));

    betsApi = jasmine.createSpyObj<BetsApiService>('BetsApiService', [
      'listBanks',
      'listPeriods',
      'listBets',
      'globalStats',
      'periodStats',
      'createBank',
      'closePeriod',
      'exportPeriod',
      'createBet',
      'resolveBet',
    ]);
    betsApi.listBanks.and.returnValue(of([bank()]));
    betsApi.listPeriods.and.returnValue(of([period()]));
    betsApi.listBets.and.returnValue(of([bet()]));
    betsApi.globalStats.and.returnValue(of(globalStats()));
    betsApi.periodStats.and.returnValue(of(periodStats()));
    betsApi.createBank.and.returnValue(of(bank()));
    betsApi.closePeriod.and.returnValue(of(period()));
    betsApi.exportPeriod.and.returnValue(of(new Blob(['x'])));
    betsApi.createBet.and.returnValue(of(bet()));
    betsApi.resolveBet.and.returnValue(of(bet({ status: 'won' })));

    gamesApi = jasmine.createSpyObj<GamesApiService>('GamesApiService', ['listGames']);
    gamesApi.listGames.and.returnValue(of(gamesResponse([game()])));

    await TestBed.configureTestingModule({
      imports: [BetsPageComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: UserAuthService, useValue: userAuth },
        { provide: BetsApiService, useValue: betsApi },
        { provide: GamesApiService, useValue: gamesApi },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(BetsPageComponent);
    component = fixture.componentInstance;
    // MatSnackBarModule (importado por el componente standalone) aporta su propia instancia,
    // así que espiamos la que el componente resuelve por su inyector en vez de un useValue raíz.
    snack = fixture.debugElement.injector.get(MatSnackBar);
    spyOn(snack, 'open');
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('ngOnInit loads session, banks and picker games when login is available', () => {
    fixture.detectChanges();
    expect(component.authReady()).toBe(true);
    expect(component.session()?.email).toBe('user@example.com');
    expect(component.banks().length).toBe(1);
    expect(component.selectedBankId()).toBe(1);
    expect(component.loading()).toBe(false);
    expect(gamesApi.listGames).toHaveBeenCalled();
  });

  it('ngOnInit short-circuits when login is unavailable', () => {
    userAuth.authReady.and.returnValue(of({ login_available: false, detail: 'apagado' }));
    fixture.detectChanges();
    expect(component.authReady()).toBe(false);
    expect(component.authDetail()).toBe('apagado');
    expect(component.loading()).toBe(false);
    expect(userAuth.checkSession).not.toHaveBeenCalled();
  });

  it('ngOnInit clears session when checkSession fails', () => {
    userAuth.checkSession.and.returnValue(throwError(() => new Error('401')));
    fixture.detectChanges();
    expect(component.session()).toBeNull();
    expect(component.loading()).toBe(false);
  });

  it('loadPickerGames filters by selected league', () => {
    const nlGame = game({
      game_pk: 888,
      home_team: { ...homeTeam, league: 'NL' },
      away_team: { ...awayTeam, league: 'NL' },
    });
    gamesApi.listGames.and.returnValue(of(gamesResponse([game(), nlGame])));
    component.pickerLeagueStr = 'NL';
    component.loadPickerGames();
    expect(component.pickerGames().length).toBe(1);
    expect(component.pickerGames()[0].game_pk).toBe(888);
    expect(component.pickerLoadingGames()).toBe(false);
  });

  it('loadPickerGames shows a snackbar on error', () => {
    gamesApi.listGames.and.returnValue(throwError(() => new Error('boom')));
    component.loadPickerGames();
    expect(component.pickerLoadingGames()).toBe(false);
    expect(snack.open).toHaveBeenCalled();
  });

  it('onGameSelect sets/clears the selected game', () => {
    component.pickerGames.set([game()]);
    component.onGameSelect(777);
    expect(component.selectedGame()?.game_pk).toBe(777);
    component.onGameSelect(null);
    expect(component.selectedGame()).toBeNull();
  });

  it('selectedGame prediction computed helpers resolve labels', () => {
    component.selectedGame.set(game());
    expect(component.selectedGamePrediction()?.home_win_probability).toBe(0.62);
    // home favored (0.62) -> uses home team abbrev
    expect(component.selectedGameFavoriteLabel()).toContain('NYY');
    // estimate 9.1 vs line 8.5 -> over
    expect(component.selectedGameRunsLean()).toBe('Sobre');
  });

  it('selectedGameRunsLean is null without a prediction', () => {
    component.selectedGame.set(game({ prediction: null }));
    expect(component.selectedGameRunsLean()).toBeNull();
  });

  it('gamePickerLabel formats teams, score, status and divisions', () => {
    const label = component.gamePickerLabel(
      game({ status: 'Final', home_score: 5, away_score: 3 }),
    );
    expect(label).toContain('BOS @ NYY');
    expect(label).toContain('(3–5)');
    expect(label).toContain('Final');
    expect(label).toContain('AL East vs AL East');
  });

  it('login delegates to startGoogleLogin', () => {
    component.login();
    expect(userAuth.startGoogleLogin).toHaveBeenCalled();
  });

  it('logout clears the session on success', () => {
    component.session.set({ email: 'user@example.com' });
    component.logout();
    expect(component.session()).toBeNull();
    expect(snack.open).toHaveBeenCalled();
  });

  it('logout falls back to clearing session locally on error', () => {
    userAuth.logout.and.returnValue(throwError(() => new Error('boom')));
    component.session.set({ email: 'user@example.com' });
    component.logout();
    expect(userAuth.clearSessionLocal).toHaveBeenCalled();
    expect(component.session()).toBeNull();
  });

  it('onBankChange resets selection and reloads', () => {
    component.onBankChange(5);
    expect(component.selectedBankId()).toBe(5);
    expect(betsApi.listPeriods).toHaveBeenCalledWith(5);
    // refreshPeriodsAndBets recarga y auto-selecciona el primer periodo (id 10).
    expect(component.selectedPeriodId()).toBe(10);
  });

  it('createBank validates inputs before calling the API', () => {
    component.newBankName = '';
    component.newBankAmount = null;
    component.createBank();
    expect(betsApi.createBank).not.toHaveBeenCalled();
    expect(snack.open).toHaveBeenCalled();
  });

  it('createBank posts valid input and resets the form', () => {
    component.newBankName = 'Secundario';
    component.newBankAmount = 500;
    component.createBank();
    expect(betsApi.createBank).toHaveBeenCalledWith({ name: 'Secundario', initial_amount: 500 });
    expect(component.newBankName).toBe('');
    expect(component.newBankAmount).toBeNull();
  });

  it('submitBet validates that bank, game, stake and odds are present', () => {
    component.selectedBankId.set(null);
    component.submitBet();
    expect(betsApi.createBet).not.toHaveBeenCalled();
    expect(snack.open).toHaveBeenCalled();
  });

  it('submitBet posts a moneyline bet', () => {
    component.selectedBankId.set(1);
    component.selectedGame.set(game());
    component.newBetType = 'moneyline';
    component.newBetSideMl = 'away';
    component.newBetStake = 25;
    component.newBetOdds = 2.1;
    component.submitBet();
    expect(betsApi.createBet).toHaveBeenCalledWith(
      jasmine.objectContaining({
        bank_id: 1,
        game_pk: 777,
        bet_type: 'moneyline',
        bet_side: 'away',
        stake: 25,
        odds: 2.1,
        ou_line: null,
      }),
    );
    expect(component.selectedGame()).toBeNull();
    expect(component.newBetStake).toBeNull();
  });

  it('submitBet requires a numeric line for over_under bets', () => {
    component.selectedBankId.set(1);
    component.selectedGame.set(game());
    component.newBetType = 'over_under';
    component.newBetSideOu = 'over';
    component.newBetStake = 25;
    component.newBetOdds = 2.0;
    component.newBetOuLine = null;
    component.submitBet();
    expect(betsApi.createBet).not.toHaveBeenCalled();
    expect(snack.open).toHaveBeenCalled();
  });

  it('submitBet posts an over_under bet with a line', () => {
    component.selectedBankId.set(1);
    component.selectedGame.set(game());
    component.newBetType = 'over_under';
    component.newBetSideOu = 'under';
    component.newBetStake = 30;
    component.newBetOdds = 1.95;
    component.newBetOuLine = 8.5;
    component.submitBet();
    expect(betsApi.createBet).toHaveBeenCalledWith(
      jasmine.objectContaining({
        bet_type: 'over_under',
        bet_side: 'under',
        ou_line: 8.5,
      }),
    );
  });

  it('resolve refreshes and notifies on success', () => {
    component.selectedBankId.set(1);
    component.resolve(bet());
    expect(betsApi.resolveBet).toHaveBeenCalledWith(100);
    expect(snack.open).toHaveBeenCalled();
  });

  it('closePeriod is a no-op without a selected period', () => {
    component.selectedPeriodId.set(null);
    component.closePeriod();
    expect(betsApi.closePeriod).not.toHaveBeenCalled();
  });

  it('closePeriod closes the selected period', () => {
    component.selectedBankId.set(1);
    component.selectedPeriodId.set(10);
    component.closePeriod();
    expect(betsApi.closePeriod).toHaveBeenCalledWith(10);
  });

  it('roiBarPct clamps the roi into 0..100', () => {
    component.globalStats.set(globalStats({ roi_pct: 20 }));
    expect(component.roiBarPct()).toBe(35);
    component.globalStats.set(globalStats({ roi_pct: 200 }));
    expect(component.roiBarPct()).toBe(100);
    component.globalStats.set(globalStats({ roi_pct: -200 }));
    expect(component.roiBarPct()).toBe(0);
    component.globalStats.set(null);
    expect(component.roiBarPct()).toBe(0);
  });

  it('statusLabel maps known statuses and falls back', () => {
    expect(component.statusLabel('won')).toBe('Ganada');
    expect(component.statusLabel('pending')).toBe('Pendiente');
    expect(component.statusLabel('weird')).toBe('weird');
  });

  it('betTypeLabel maps bet types', () => {
    expect(component.betTypeLabel('moneyline')).toBe('Ganador');
    expect(component.betTypeLabel('over_under')).toBe('Más/menos');
  });
});
