import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';

const TABS = ['/mlb/today', '/mlb/tomorrow', '/mlb/week', '/mlb/history'] as const;

@Component({
  selector: 'app-mlb-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
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
    // En rutas sin tab propio (p. ej. detalle de partido /mlb/game/:id) mantenemos
    // el tab anterior, para que la píldora y el texto en blanco no se desincronicen.
    if (idx >= 0) {
      this.activeIndex.set(idx);
    }
  }
}
