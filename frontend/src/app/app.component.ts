import { Component, OnInit, inject } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import { filter } from 'rxjs/operators';

import type { SportId } from './models/sport';
import { SPORT_OPTIONS, sportIdFromUrl } from './models/sport';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    RouterLink,
    MatToolbarModule,
    MatButtonModule,
    MatFormFieldModule,
    MatSelectModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  private readonly router = inject(Router);

  readonly title = 'Sports Predictions';
  readonly sports = SPORT_OPTIONS;
  sport: SportId = 'mlb';

  ngOnInit(): void {
    this.sport = sportIdFromUrl(this.router.url);
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(() => {
        this.sport = sportIdFromUrl(this.router.url);
      });
  }

  onSportChange(id: SportId): void {
    if (id === 'mlb') {
      void this.router.navigate(['/mlb']);
    } else if (id === 'soccer') {
      void this.router.navigate(['/soccer']);
    } else {
      void this.router.navigate(['/nba']);
    }
  }
}
