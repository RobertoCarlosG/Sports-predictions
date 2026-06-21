import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  computed,
  inject,
  output,
} from '@angular/core';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { MatBadgeModule } from '@angular/material/badge';
import { MatIconModule } from '@angular/material/icon';
import { filter, Subscription } from 'rxjs';
import { MatIconButton } from '@angular/material/button';
import { BreakpointObserver } from '@angular/cdk/layout';

import { SPORT_OPTIONS, type SportId, type SportOption } from '../../models/sport';
import { FeaturesService } from '../../services/features.service';
import { NotificationService } from '../../services/notification.service';
import { ThemeService } from '../../services/theme.service';

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
  private readonly breakpoint = inject(BreakpointObserver);
  protected readonly notif = inject(NotificationService);
  protected readonly themeSvc = inject(ThemeService);
  private readonly featuresSvc = inject(FeaturesService);
  private sub: Subscription | null = null;
  private bpSub: Subscription | null = null;

  readonly closeRequest = output<void>();

  readonly title = 'Sports Predictions';
  readonly sports = computed(() =>
    SPORT_OPTIONS.map((s) =>
      s.id === 'nba' ? { ...s, implemented: this.featuresSvc.nbaEnabled() } : s,
    ),
  );
  private url = '';
  collapsed = false;
  isMobile = false;

  toggleCollapse() {
    this.collapsed = !this.collapsed;
  }

  ngOnInit(): void {
    this.url = this.stripQuery(this.router.url);
    this.sub = this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(() => {
        this.url = this.stripQuery(this.router.url);
        if (this.isMobile) this.closeRequest.emit();
        this.cdr.markForCheck();
      });

    this.bpSub = this.breakpoint.observe('(max-width: 767px)').subscribe(state => {
      this.isMobile = state.matches;
      this.cdr.markForCheck();
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.bpSub?.unsubscribe();
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
