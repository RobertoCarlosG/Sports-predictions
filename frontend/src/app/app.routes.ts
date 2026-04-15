import { Routes } from '@angular/router';

import { ComingSoonComponent } from './coming-soon/coming-soon.component';
import { GameDetailComponent } from './game-detail/game-detail.component';
import { GameListComponent } from './game-list/game-list.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'mlb' },
  {
    path: 'mlb',
    children: [
      { path: '', component: GameListComponent },
      { path: 'game/:gamePk', component: GameDetailComponent },
    ],
  },
  {
    path: 'soccer',
    component: ComingSoonComponent,
    data: {
      title: 'Fútbol',
      subtitle: 'API-Sports y datos de ligas — en construcción',
    },
  },
  {
    path: 'nba',
    component: ComingSoonComponent,
    data: {
      title: 'NBA',
      subtitle: 'Baloncesto — en construcción',
    },
  },
  { path: '**', redirectTo: 'mlb' },
];
