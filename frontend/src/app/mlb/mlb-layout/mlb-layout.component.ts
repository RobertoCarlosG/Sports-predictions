import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';

const TABS = ['/mlb/today', '/mlb/tomorrow', '/mlb/week', '/mlb/history'] as const;

@Component({
  selector: 'app-mlb-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './mlb-layout.component.html',
  styleUrl: './mlb-layout.component.scss',
})
export class MlbLayoutComponent {
  activeIndex = signal(0);

  constructor() {
    const router = inject(Router);

    this.updateIndex(router.url);

    router.events
      .pipe(filter(e => e instanceof NavigationEnd), takeUntilDestroyed())
      .subscribe(e => this.updateIndex((e as NavigationEnd).urlAfterRedirects));
  }

  private updateIndex(url: string): void {
    const idx = TABS.findIndex(t => url.startsWith(t));
    this.activeIndex.set(idx >= 0 ? idx : 0);
  }
}
