import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'mlb' },
  {
    path: 'mlb',
    children: [
      {
        path: '',
        loadComponent: () =>
          import('./game-list/game-list.component').then((m) => m.GameListComponent),
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
  { path: '**', redirectTo: 'mlb' },
];
