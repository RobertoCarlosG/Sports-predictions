import { DatePipe } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSidenavModule } from '@angular/material/sidenav';

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
    DatePipe,
  ],
  templateUrl: './main-layout.component.html',
  styleUrl: './main-layout.component.scss',
})
export class MainLayoutComponent implements OnInit {
  private readonly modelInfo = inject(ModelInfoService);
  protected readonly notif = inject(NotificationService);

  protected readonly notifOpen = this.notif.panelOpen;
  protected readonly notifications = this.notif.notifications;

  ngOnInit(): void {
    this.modelInfo.start();
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
