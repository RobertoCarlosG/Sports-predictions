import { TestBed } from '@angular/core/testing';

import { NotificationService } from './notification.service';

describe('NotificationService', () => {
  let service: NotificationService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [NotificationService] });
    service = TestBed.inject(NotificationService);
  });

  it('creates', () => expect(service).toBeTruthy());

  it('starts empty with panel closed and zero unread', () => {
    expect(service.notifications()).toEqual([]);
    expect(service.panelOpen()).toBe(false);
    expect(service.unreadCount()).toBe(0);
  });

  it('push() prepends a notification with defaults and increments unread', () => {
    service.push('hello');
    const list = service.notifications();
    expect(list.length).toBe(1);
    expect(list[0].message).toBe('hello');
    expect(list[0].type).toBe('info');
    expect(list[0].read).toBe(false);
    expect(list[0].id).toBe(1);
    expect(list[0].timestamp instanceof Date).toBe(true);
    expect(service.unreadCount()).toBe(1);
  });

  it('push() honors explicit type and prepends newest first with incrementing ids', () => {
    service.push('first', 'success');
    service.push('second', 'error');
    const list = service.notifications();
    expect(list[0].message).toBe('second');
    expect(list[0].type).toBe('error');
    expect(list[0].id).toBe(2);
    expect(list[1].message).toBe('first');
    expect(list[1].id).toBe(1);
    expect(service.unreadCount()).toBe(2);
  });

  it('push() caps the list at 50 entries', () => {
    for (let i = 0; i < 55; i++) {
      service.push(`m${i}`);
    }
    expect(service.notifications().length).toBe(50);
    // Newest first: the last pushed message is at the head.
    expect(service.notifications()[0].message).toBe('m54');
  });

  it('markAllRead() marks every notification read and zeroes unread', () => {
    service.push('a');
    service.push('b');
    service.markAllRead();
    expect(service.unreadCount()).toBe(0);
    expect(service.notifications().every((n) => n.read)).toBe(true);
  });

  it('openPanel() opens the panel and marks all read', () => {
    service.push('a');
    service.openPanel();
    expect(service.panelOpen()).toBe(true);
    expect(service.unreadCount()).toBe(0);
  });

  it('closePanel() closes the panel', () => {
    service.openPanel();
    service.closePanel();
    expect(service.panelOpen()).toBe(false);
  });

  it('togglePanel() toggles between open and closed', () => {
    expect(service.panelOpen()).toBe(false);
    service.togglePanel();
    expect(service.panelOpen()).toBe(true);
    service.togglePanel();
    expect(service.panelOpen()).toBe(false);
  });

  it('togglePanel() opening also marks read', () => {
    service.push('a');
    service.togglePanel();
    expect(service.panelOpen()).toBe(true);
    expect(service.unreadCount()).toBe(0);
  });
});
