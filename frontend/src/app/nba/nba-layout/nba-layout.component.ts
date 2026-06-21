import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';

const TABS = ['/nba/today', '/nba/tomorrow', '/nba/week'] as const;

@Component({
  selector: 'app-nba-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  templateUrl: './nba-layout.component.html',
  styleUrl: './nba-layout.component.scss',
})
export class NbaLayoutComponent {
  activeIndex = signal(0);

  constructor() {
    const router = inject(Router);
    this.updateIndex(router.url);
    router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((e) => this.updateIndex((e as NavigationEnd).urlAfterRedirects));
  }

  private updateIndex(url: string): void {
    const idx = TABS.findIndex((t) => url.startsWith(t));
    if (idx >= 0) {
      this.activeIndex.set(idx);
    }
  }
}
