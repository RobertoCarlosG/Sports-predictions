import { DatePipe } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatBadgeModule } from '@angular/material/badge';
import { BreakpointObserver } from '@angular/cdk/layout';
import { Subscription } from 'rxjs';

import { ModelInfoService } from '../../services/model-info.service';
import { NotificationService, type NotifType } from '../../services/notification.service';
import { ModelFooterComponent } from '../model-footer/model-footer.component';
import { SidebarComponent } from '../sidebar/sidebar.component';

/**
 * El shell usa detección por defecto: con OnPush, las actualizaciones asíncronas (p. ej. HttpClient) en
 * componentes cargados bajo <router-outlet> no hacían que este padre se volviera a comprobar, y la vista
 * solo se actualizaba tras un evento de UI (p. ej. focus en un input).
 */
@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [
    SidebarComponent,
    RouterOutlet,
    ModelFooterComponent,
    MatSidenavModule,
    MatButtonModule,
    MatIconModule,
    MatBadgeModule,
    DatePipe,
  ],
  templateUrl: './main-layout.component.html',
  styleUrl: './main-layout.component.scss',
})
export class MainLayoutComponent implements OnInit, OnDestroy {
  private readonly modelInfo = inject(ModelInfoService);
  private readonly breakpoint = inject(BreakpointObserver);
  private bpSub: Subscription | null = null;
  protected readonly notif = inject(NotificationService);

  protected readonly notifOpen = this.notif.panelOpen;
  protected readonly notifications = this.notif.notifications;

  protected readonly isMobile = signal(false);
  protected readonly mobileSidebarOpen = signal(false);

  ngOnInit(): void {
    this.modelInfo.start();
    this.bpSub = this.breakpoint.observe('(max-width: 767px)').subscribe(state => {
      this.isMobile.set(state.matches);
      if (!state.matches) this.mobileSidebarOpen.set(false);
    });
  }

  ngOnDestroy(): void {
    this.bpSub?.unsubscribe();
  }

  protected openMobileSidebar(): void {
    this.mobileSidebarOpen.set(true);
  }

  protected closeMobileSidebar(): void {
    this.mobileSidebarOpen.set(false);
  }

  protected notifIcon(type: NotifType): string {
    const icons: Record<NotifType, string> = {
      info: 'info',
      success: 'check_circle',
      warn: 'warning_amber',
      error: 'error_outline',
    };
    return icons[type];
  }
}
