import { Component, OnInit, inject } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatToolbarModule } from '@angular/material/toolbar';
import { filter } from 'rxjs/operators';

import { SportTabNavComponent } from './components/sport-tab-nav/sport-tab-nav.component';
import type { SportId } from './models/sport';
import { sportIdFromUrl } from './models/sport';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, MatToolbarModule, MatButtonModule, SportTabNavComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  private readonly router = inject(Router);

  readonly title = 'Sports Predictions';
  sport: SportId = 'mlb';

  ngOnInit(): void {
    this.sport = sportIdFromUrl(this.router.url);
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(() => {
        this.sport = sportIdFromUrl(this.router.url);
      });
  }
}
