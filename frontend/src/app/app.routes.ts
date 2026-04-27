import { Routes } from '@angular/router';

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
        path: 'nba',
        loadComponent: () =>
          import('./coming-soon/coming-soon.component').then((m) => m.ComingSoonComponent),
        data: {
          title: 'NBA',
          subtitle: 'Baloncesto — en construcción',
        },
      },
      {
        path: 'operations',
        loadComponent: () =>
          import('./operations/operations.component').then((m) => m.OperationsComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'mlb/today' },
];
