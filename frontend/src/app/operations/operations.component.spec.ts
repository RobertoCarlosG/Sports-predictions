import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import {
  AdminApiService,
  type AdminAuthReadyResponse,
  type AdminSessionResponse,
  type BackfillJobStatusResponse,
  type MessageResponse,
} from '../services/admin-api.service';
import { GamesApiService } from '../services/games-api.service';
import { ModelInfoService } from '../services/model-info.service';
import { NotificationService } from '../services/notification.service';
import { OperationsComponent } from './operations.component';

function authReady(overrides: Partial<AdminAuthReadyResponse> = {}): AdminAuthReadyResponse {
  return { login_available: true, detail: null, ...overrides };
}

function session(overrides: Partial<AdminSessionResponse> = {}): AdminSessionResponse {
  return {
    username: 'admin',
    token_expires_at: '2026-06-16T12:00:00Z',
    token_ttl_minutes: 60,
    seconds_until_expiry: 1800,
    ...overrides,
  };
}

function backfillStatus(
  overrides: Partial<BackfillJobStatusResponse> = {},
): BackfillJobStatusResponse {
  return {
    status: 'idle',
    job_id: null,
    started_at: null,
    finished_at: null,
    date_start: null,
    date_end: null,
    days_total: 0,
    days_done: 0,
    current_date: null,
    error_detail: null,
    result_message: null,
    ...overrides,
  };
}

const message: MessageResponse = { message: 'ok', detail: 'Versión activa: rf-db-v1.' };

describe('OperationsComponent', () => {
  let fixture: ComponentFixture<OperationsComponent>;
  let component: OperationsComponent;
  let admin: jasmine.SpyObj<AdminApiService>;
  let games: jasmine.SpyObj<GamesApiService>;
  let modelInfo: jasmine.SpyObj<ModelInfoService>;
  let notif: jasmine.SpyObj<NotificationService>;
  let dialog: jasmine.SpyObj<MatDialog>;
  let snack: jasmine.SpyObj<MatSnackBar>;

  beforeEach(async () => {
    admin = jasmine.createSpyObj<AdminApiService>('AdminApiService', [
      'authReady',
      'checkSession',
      'isLoggedIn',
      'clearSessionLocal',
      'login',
      'logout',
      'refreshSession',
      'status',
      'rebuildSnapshots',
      'clearPredictionCache',
      'fixFifty',
      'reloadModel',
      'reloadModelXgb',
      'reloadNbaModels',
      'nbaRebuildSnapshots',
      'calibrateModel',
      'trainModel',
      'backfill',
      'getBackfillStatus',
      'runMlbDailySnapshot',
    ]);
    // authReady returns null (not login_available) by default to keep ngOnInit quiet.
    admin.authReady.and.returnValue(of(authReady({ login_available: false })));
    admin.checkSession.and.returnValue(of(session()));
    admin.isLoggedIn.and.returnValue(false);
    admin.login.and.returnValue(of(session()));
    admin.logout.and.returnValue(of(message));
    admin.refreshSession.and.returnValue(of(session()));
    admin.status.and.returnValue(of(message));
    admin.rebuildSnapshots.and.returnValue(of(message));
    admin.clearPredictionCache.and.returnValue(of(message));
    admin.fixFifty.and.returnValue(of(message));
    admin.reloadModel.and.returnValue(of(message));
    admin.reloadModelXgb.and.returnValue(of(message));
    admin.reloadNbaModels.and.returnValue(of(message));
    admin.nbaRebuildSnapshots.and.returnValue(of(message));
    admin.calibrateModel.and.returnValue(of(message));
    admin.trainModel.and.returnValue(of({ message: 'trained', stdout_tail: 'tail' }));
    admin.backfill.and.returnValue(of({ ...message, job_id: 'job-1' }));
    admin.getBackfillStatus.and.returnValue(of(backfillStatus()));
    admin.runMlbDailySnapshot.and.returnValue(of(message));

    games = jasmine.createSpyObj<GamesApiService>('GamesApiService', ['syncMlbRange']);
    games.syncMlbRange.and.returnValue(
      of({ start_date: '2026-06-16', end_date: '2026-06-16', days_synced: 1 }),
    );

    modelInfo = jasmine.createSpyObj<ModelInfoService>('ModelInfoService', ['refreshOnce']);
    // info / isSynthetic are signal properties read by the component.
    (modelInfo as unknown as { info: unknown }).info = signal(null);
    (modelInfo as unknown as { isSynthetic: unknown }).isSynthetic = signal(false);

    notif = jasmine.createSpyObj<NotificationService>('NotificationService', ['push']);

    dialog = jasmine.createSpyObj<MatDialog>('MatDialog', ['open']);
    dialog.open.and.returnValue({ afterClosed: () => of(null) } as never);

    snack = jasmine.createSpyObj<MatSnackBar>('MatSnackBar', ['open']);

    await TestBed.configureTestingModule({
      imports: [OperationsComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AdminApiService, useValue: admin },
        { provide: GamesApiService, useValue: games },
        { provide: ModelInfoService, useValue: modelInfo },
        { provide: NotificationService, useValue: notif },
        { provide: MatDialog, useValue: dialog },
        { provide: MatSnackBar, useValue: snack },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(OperationsComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    expect(component).toBeTruthy();
  });

  it('loggedIn() delegates to the admin service', () => {
    admin.isLoggedIn.and.returnValue(true);
    expect(component.loggedIn()).toBe(true);
    admin.isLoggedIn.and.returnValue(false);
    expect(component.loggedIn()).toBe(false);
  });

  it('operationsLocked reflects busy and backfillTracking', () => {
    expect(component.operationsLocked).toBe(false);
    component.busy = true;
    expect(component.operationsLocked).toBe(true);
    component.busy = false;
    component.backfillTracking = true;
    expect(component.operationsLocked).toBe(true);
  });

  it('backfillProgressPercent computes a clamped percentage', () => {
    expect(component.backfillProgressPercent).toBe(0);
    component.backfillStatus = backfillStatus({ days_total: 10, days_done: 3 });
    expect(component.backfillProgressPercent).toBe(30);
    component.backfillStatus = backfillStatus({ days_total: 10, days_done: 100 });
    expect(component.backfillProgressPercent).toBe(100);
  });

  it('backfillPhaseLabel maps job status', () => {
    component.backfillStatus = backfillStatus({ status: 'queued' });
    expect(component.backfillPhaseLabel).toBe('En cola…');
    component.backfillStatus = backfillStatus({ status: 'running' });
    expect(component.backfillPhaseLabel).toBe('Sincronizando fechas con la API de MLB…');
    component.backfillStatus = backfillStatus({ status: 'success' });
    expect(component.backfillPhaseLabel).toBe('');
  });

  it('parseModelVersionFromDetail extracts the active version', () => {
    const parse = (
      component as unknown as { parseModelVersionFromDetail(d: string | null): string }
    ).parseModelVersionFromDetail.bind(component);
    expect(parse(null)).toBe('—');
    expect(parse('')).toBe('—');
    expect(parse('Algo sin versión')).toBe('—');
    expect(parse('Versión activa: rf-db-v1.')).toBe('rf-db-v1');
    expect(parse('Estado. Versión activa: xgb-v2 ')).toBe('xgb-v2');
  });

  it('refreshStatus stores status text and parsed version', () => {
    component.refreshStatus();
    expect(component.statusText).toBe('ok');
    expect(component.activeModelVersion).toBe('rf-db-v1');
  });

  it('login applies session hint on success', () => {
    component.username = 'admin';
    component.password = 'pw';
    component.login();
    expect(admin.login).toHaveBeenCalledWith('admin', 'pw');
    expect(component.loginLoading).toBe(false);
    expect(component.password).toBe('');
    expect(component.sessionHint).toContain('Sesión');
  });

  it('rebuildSnapshots runs the admin op and opens a dialog', () => {
    component.seasonFilter = ' 2024 ';
    component.snapshotWindow = 7;
    component.rebuildSnapshots();
    expect(admin.rebuildSnapshots).toHaveBeenCalledWith('2024', 7);
    expect(component.busy).toBe(false);
    expect(dialog.open).toHaveBeenCalled();
    expect(notif.push).toHaveBeenCalled();
  });

  it('rebuildNbaSnapshots forwards trimmed season and window', () => {
    component.nbaSeasonFilter = ' 2023-24 ';
    component.nbaSnapshotWindow = 8;
    component.rebuildNbaSnapshots();
    expect(admin.nbaRebuildSnapshots).toHaveBeenCalledWith('2023-24', 8);
    expect(component.busy).toBe(false);
    expect(dialog.open).toHaveBeenCalled();
  });

  it('reloadNbaModels runs the op and refreshes model info', () => {
    component.reloadNbaModels();
    expect(admin.reloadNbaModels).toHaveBeenCalled();
    expect(modelInfo.refreshOnce).toHaveBeenCalled();
  });

  it('fixFifty refreshes model info on success', () => {
    component.fixFifty();
    expect(admin.fixFifty).toHaveBeenCalled();
    expect(modelInfo.refreshOnce).toHaveBeenCalled();
  });

  it('train forwards hyperparameters with defaults', () => {
    component.trainSeason = ' 2024 ';
    component.trainModelVersion = '';
    component.train();
    expect(admin.trainModel).toHaveBeenCalledWith(
      jasmine.objectContaining({ season: '2024', model_version: 'rf-db-v1' }),
    );
  });

  it('trainStepNext / trainStepBack stay within bounds', () => {
    component.trainStep = 1;
    component.trainStepBack();
    expect(component.trainStep).toBe(1);
    component.trainStepNext();
    expect(component.trainStep).toBe(2);
    component.trainStepNext();
    component.trainStepNext();
    expect(component.trainStep).toBe(component.trainTotalSteps);
  });

  it('backfill validates required dates', () => {
    component.backfillStart = '';
    component.backfillEnd = '';
    component.backfill();
    expect(admin.backfill).not.toHaveBeenCalled();
    expect(dialog.open).toHaveBeenCalled();
  });

  it('syncTodayAndTomorrow calls the games sync and stops loading', () => {
    component.syncTodayAndTomorrow();
    expect(games.syncMlbRange).toHaveBeenCalled();
    expect(component.quickSyncLoading).toBe(false);
    expect(component.lastQuickSyncAt).not.toBeNull();
  });

  it('logout clears local state', () => {
    component.statusText = 'something';
    component.logout();
    expect(admin.logout).toHaveBeenCalled();
    expect(component.statusText).toBeNull();
    expect(component.activeModelVersion).toBe('—');
  });
});
