import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  inject,
} from '@angular/core';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { filter, Subscription } from 'rxjs';

import { SPORT_OPTIONS, type SportId, type SportOption } from '../../models/sport';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, MatIconModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent implements OnInit, OnDestroy {
  private readonly router = inject(Router);
  private readonly cdr = inject(ChangeDetectorRef);
  private sub: Subscription | null = null;

  readonly title = 'Sports Predictions';
  readonly sports = SPORT_OPTIONS;
  private url = '';

  ngOnInit(): void {
    this.url = this.stripQuery(this.router.url);
    this.sub = this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(() => {
        this.url = this.stripQuery(this.router.url);
        this.cdr.markForCheck();
      });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  pathFor(id: SportId): string {
    if (id === 'mlb') {
      return '/mlb';
    }
    if (id === 'soccer') {
      return '/soccer';
    }
    return '/nba';
  }

  sportRowActive(s: SportOption): boolean {
    return this.pathActive(this.pathFor(s.id));
  }

  linkActiveOperations(): boolean {
    return this.pathActive('/operations');
  }

  private pathActive(prefix: string): boolean {
    if (prefix === '/operations') {
      return this.url === '/operations' || this.url.startsWith('/operations/');
    }
    return this.url === prefix || this.url.startsWith(`${prefix}/`);
  }

  private stripQuery(path: string): string {
    return path.split('?')[0] ?? '';
  }
}
