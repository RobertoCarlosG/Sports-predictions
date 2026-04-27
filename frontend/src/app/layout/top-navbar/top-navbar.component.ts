import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  inject,
} from '@angular/core';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatToolbarModule } from '@angular/material/toolbar';
import { filter, Subscription } from 'rxjs';

import { SportTabNavComponent } from '../../components/sport-tab-nav/sport-tab-nav.component';
import type { SportId } from '../../models/sport';
import { activeSportIdFromUrl } from '../../models/sport';

@Component({
  selector: 'app-top-navbar',
  standalone: true,
  imports: [RouterLink, MatToolbarModule, MatButtonModule, MatIconModule, SportTabNavComponent],
  templateUrl: './top-navbar.component.html',
  styleUrl: './top-navbar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TopNavbarComponent implements OnInit, OnDestroy {
  private readonly router = inject(Router);
  private readonly cdr = inject(ChangeDetectorRef);
  private sub: Subscription | null = null;

  readonly title = 'Sports Predictions';
  activeSport: SportId | null = 'mlb';

  ngOnInit(): void {
    this.activeSport = activeSportIdFromUrl(this.router.url);
    this.sub = this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(() => {
        this.activeSport = activeSportIdFromUrl(this.router.url);
        this.cdr.markForCheck();
      });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
