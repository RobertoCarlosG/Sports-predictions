import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  inject,
} from '@angular/core';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { MatBadgeModule } from '@angular/material/badge';
import { MatIconModule } from '@angular/material/icon';
import { filter, Subscription } from 'rxjs';
import { MatIconButton } from '@angular/material/button';

import { SPORT_OPTIONS, type SportId, type SportOption } from '../../models/sport';
import { NotificationService } from '../../services/notification.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, MatBadgeModule, MatIconModule, MatIconButton],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent implements OnInit, OnDestroy {
  private readonly router = inject(Router);
  private readonly cdr = inject(ChangeDetectorRef);
  protected readonly notif = inject(NotificationService);
  private sub: Subscription | null = null;

  readonly title = 'Sports Predictions';
  readonly sports = SPORT_OPTIONS;
  private url = '';
  collapsed = false;

  toggleCollapse() {
    this.collapsed = !this.collapsed;
  }

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

  linkActiveBets(): boolean {
    return this.pathActive('/bets');
  }

  private pathActive(prefix: string): boolean {
    if (prefix === '/operations') {
      return this.url === '/operations' || this.url.startsWith('/operations/');
    }
    if (prefix === '/bets') {
      return this.url === '/bets' || this.url.startsWith('/bets/');
    }
    return this.url === prefix || this.url.startsWith(`${prefix}/`);
  }

  private stripQuery(path: string): string {
    return path.split('?')[0] ?? '';
  }
}
