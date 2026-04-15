import { Routes } from '@angular/router';

import { GameDetailComponent } from './game-detail/game-detail.component';
import { GameListComponent } from './game-list/game-list.component';

export const routes: Routes = [
  { path: '', component: GameListComponent },
  { path: 'games/:gamePk', component: GameDetailComponent },
  { path: '**', redirectTo: '' },
];
