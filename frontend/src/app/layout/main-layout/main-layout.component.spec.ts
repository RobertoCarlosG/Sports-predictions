import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { ModelInfoService } from '../../services/model-info.service';
import { NotificationService } from '../../services/notification.service';
import { MainLayoutComponent } from './main-layout.component';

describe('MainLayoutComponent', () => {
  let fixture: ComponentFixture<MainLayoutComponent>;
  let component: MainLayoutComponent;
  let modelInfoSpy: { start: jasmine.Spy; refreshOnce: jasmine.Spy };

  beforeEach(async () => {
    modelInfoSpy = {
      start: jasmine.createSpy('start'),
      refreshOnce: jasmine.createSpy('refreshOnce'),
    };
    const modelInfo = {
      info: signal(null),
      shortLabel: signal('Modelo no cargado'),
      isSynthetic: signal(false),
      start: modelInfoSpy.start,
      refreshOnce: modelInfoSpy.refreshOnce,
    };

    await TestBed.configureTestingModule({
      imports: [MainLayoutComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ModelInfoService, useValue: modelInfo },
        NotificationService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(MainLayoutComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('creates the shell', () => {
    expect(component).toBeTruthy();
  });

  it('starts the model-info polling on init', () => {
    expect(modelInfoSpy.start).toHaveBeenCalled();
  });

  it('renders a router-outlet', () => {
    const outlet = fixture.nativeElement.querySelector('router-outlet');
    expect(outlet).not.toBeNull();
  });

  it('maps notification types to material icons', () => {
    const notifIcon = (component as unknown as {
      notifIcon: (t: string) => string;
    }).notifIcon.bind(component);
    expect(notifIcon('info')).toBe('info');
    expect(notifIcon('success')).toBe('check_circle');
    expect(notifIcon('warn')).toBe('warning_amber');
    expect(notifIcon('error')).toBe('error_outline');
  });
});
