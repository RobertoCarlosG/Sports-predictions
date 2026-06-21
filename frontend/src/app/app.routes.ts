import { Routes } from '@angular/router';

import { authGuard } from './guards/auth.guard';
import { nbaFeatureGuard } from './guards/nba-feature.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./layout/main-layout/main-layout.component').then((m) => m.MainLayoutComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'mlb/today' },
      {
        path: 'mlb',
        loadComponent: () =>
          import('./mlb/mlb-layout/mlb-layout.component').then((m) => m.MlbLayoutComponent),
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'today' },
          {
            path: 'dashboard',
            pathMatch: 'full',
            redirectTo: '/operations',
          },
          {
            path: 'today',
            loadComponent: () =>
              import('./game-list/game-list.component').then((m) => m.GameListComponent),
            data: { datePreset: 'today' as const },
          },
          {
            path: 'tomorrow',
            loadComponent: () =>
              import('./game-list/game-list.component').then((m) => m.GameListComponent),
            data: { datePreset: 'tomorrow' as const },
          },
          {
            path: 'week',
            loadComponent: () =>
              import('./game-list/game-list.component').then((m) => m.GameListComponent),
            data: { datePreset: 'week' as const },
          },
          {
            path: 'history',
            loadComponent: () =>
              import('./mlb-history/mlb-history.component').then((m) => m.MlbHistoryComponent),
            canActivate: [authGuard],
          },
          {
            path: 'game/:gamePk',
            loadComponent: () =>
              import('./game-detail/game-detail.component').then((m) => m.GameDetailComponent),
          },
        ],
      },
      {
        path: 'soccer',
        loadComponent: () =>
          import('./coming-soon/coming-soon.component').then((m) => m.ComingSoonComponent),
        data: {
          title: 'Fútbol',
          subtitle: 'API-Sports y datos de ligas — en construcción',
        },
      },
      {
        path: 'nba-coming-soon',
        loadComponent: () =>
          import('./coming-soon/coming-soon.component').then((m) => m.ComingSoonComponent),
        data: {
          title: 'NBA',
          subtitle: 'NBA — stats.nba.com (XGBoost / LightGBM / CatBoost) — en construcción',
        },
      },
      {
        path: 'nba',
        canActivate: [nbaFeatureGuard],
        loadComponent: () =>
          import('./nba/nba-layout/nba-layout.component').then((m) => m.NbaLayoutComponent),
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'today' },
          {
            path: 'today',
            loadComponent: () =>
              import('./nba/nba-game-list/nba-game-list.component').then(
                (m) => m.NbaGameListComponent,
              ),
            data: { datePreset: 'today' as const },
          },
          {
            path: 'tomorrow',
            loadComponent: () =>
              import('./nba/nba-game-list/nba-game-list.component').then(
                (m) => m.NbaGameListComponent,
              ),
            data: { datePreset: 'tomorrow' as const },
          },
          {
            path: 'week',
            loadComponent: () =>
              import('./nba/nba-game-list/nba-game-list.component').then(
                (m) => m.NbaGameListComponent,
              ),
            data: { datePreset: 'week' as const },
          },
          {
            path: 'game/:gameId',
            loadComponent: () =>
              import('./nba/nba-game-detail/nba-game-detail.component').then(
                (m) => m.NbaGameDetailComponent,
              ),
          },
        ],
      },
      {
        path: 'operations',
        loadComponent: () =>
          import('./operations/operations.component').then((m) => m.OperationsComponent),
      },
      {
        path: 'bets',
        loadComponent: () => import('./bets/bets-page.component').then((m) => m.BetsPageComponent),
      },
    ],
  },
  {
    path: 'login',
    loadComponent: () =>
      import('./login/login-page.component').then((m) => m.LoginPageComponent),
  },
  { path: '**', redirectTo: 'mlb/today' },
];
