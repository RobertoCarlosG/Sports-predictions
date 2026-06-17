import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { FriendlyErrorBannerComponent } from './friendly-error-banner.component';

describe('FriendlyErrorBannerComponent', () => {
  let fixture: ComponentFixture<FriendlyErrorBannerComponent>;
  let component: FriendlyErrorBannerComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FriendlyErrorBannerComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(FriendlyErrorBannerComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('renders default message and retry label', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.msg')?.textContent).toContain(
      'No pudimos cargar los datos.',
    );
    expect(fixture.nativeElement.querySelector('button')?.textContent).toContain(
      'Intentar de nuevo',
    );
  });

  it('renders a custom message and label', () => {
    component.message = 'Error de red';
    component.retryLabel = 'Reintentar';
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.msg')?.textContent).toContain('Error de red');
    expect(fixture.nativeElement.querySelector('button')?.textContent).toContain('Reintentar');
  });

  it('emits retry when the button is clicked', () => {
    fixture.detectChanges();
    const spy = jasmine.createSpy('retry');
    component.retry.subscribe(spy);
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    button.click();
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
