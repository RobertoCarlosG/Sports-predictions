import { Injectable, computed, signal } from '@angular/core';

export type NotifType = 'info' | 'success' | 'warn' | 'error';

export interface AppNotification {
  id: number;
  type: NotifType;
  message: string;
  timestamp: Date;
  read: boolean;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private counter = 0;

  readonly notifications = signal<AppNotification[]>([]);
  readonly panelOpen = signal(false);
  readonly unreadCount = computed(() =>
    this.notifications().filter((n) => !n.read).length,
  );

  push(message: string, type: NotifType = 'info'): void {
    const notif: AppNotification = {
      id: ++this.counter,
      type,
      message,
      timestamp: new Date(),
      read: false,
    };
    this.notifications.update((prev) => [notif, ...prev].slice(0, 50));
  }

  markAllRead(): void {
    this.notifications.update((prev) => prev.map((n) => ({ ...n, read: true })));
  }

  openPanel(): void {
    this.panelOpen.set(true);
    this.markAllRead();
  }

  closePanel(): void {
    this.panelOpen.set(false);
  }

  togglePanel(): void {
    if (this.panelOpen()) {
      this.closePanel();
    } else {
      this.openPanel();
    }
  }
}
