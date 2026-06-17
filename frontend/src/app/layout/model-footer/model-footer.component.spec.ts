import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { WritableSignal, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { ModelFooterComponent } from './model-footer.component';
import { ModelInfoService, PublicModelInfo } from '../../services/model-info.service';

describe('ModelFooterComponent', () => {
  let fixture: ComponentFixture<ModelFooterComponent>;
  let component: ModelFooterComponent;
  let infoSignal: WritableSignal<PublicModelInfo | null>;

  function setup(initial: PublicModelInfo | null): void {
    infoSignal = signal<PublicModelInfo | null>(initial);

    const stub = {
      info: infoSignal,
      shortLabel: signal('Modelo no cargado'),
      isSynthetic: signal(false),
      start: jasmine.createSpy('start'),
      refreshOnce: jasmine.createSpy('refreshOnce'),
    };

    TestBed.configureTestingModule({
      imports: [ModelFooterComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ModelInfoService, useValue: stub },
      ],
    });

    fixture = TestBed.createComponent(ModelFooterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('creates', () => {
    setup(null);
    expect(component).toBeTruthy();
  });

  it('renders nothing when info is null', () => {
    setup(null);
    expect(fixture.nativeElement.querySelector('footer.model-footer')).toBeNull();
  });

  it('renders the base_version label for a trained model', () => {
    setup({
      model_loaded: true,
      base_version: 'rf-db-v1',
      is_synthetic: false,
      loaded_at: '2026-06-01T12:00:00Z',
    });
    const label = fixture.nativeElement.querySelector('.model-footer__label');
    expect((label.textContent as string).trim()).toBe('rf-db-v1');
  });

  it('marks the footer as synthetic and shows the science icon', () => {
    setup({
      model_loaded: true,
      base_version: 'rf-db-v1',
      is_synthetic: true,
      loaded_at: null,
    });
    const footer = fixture.nativeElement.querySelector('footer.model-footer');
    expect(footer.classList).toContain('model-footer--synthetic');
    const label = fixture.nativeElement.querySelector('.model-footer__label');
    expect((label.textContent as string).trim()).toBe('Modelo sintético (fallback)');
    const icon = fixture.nativeElement.querySelector('mat-icon.model-footer__icon');
    expect((icon.textContent as string).trim()).toBe('science');
  });

  it('marks the footer as missing when model is not loaded', () => {
    setup({ model_loaded: false });
    const footer = fixture.nativeElement.querySelector('footer.model-footer');
    expect(footer.classList).toContain('model-footer--missing');
    const label = fixture.nativeElement.querySelector('.model-footer__label');
    expect((label.textContent as string).trim()).toBe('Modelo no cargado');
  });

  it('computes a descriptive tooltip for a trained model', () => {
    setup({
      model_loaded: true,
      model_version: 'rf-db-v1',
      is_synthetic: false,
      loaded_at: '2026-06-01T12:00:00Z',
    });
    const tooltip = component['tooltip']();
    expect(tooltip).toContain('Modelo: rf-db-v1');
    expect(tooltip).toContain('entrenado contra base de datos');
    expect(tooltip).toContain('Cargado: 2026-06-01T12:00:00Z');
  });

  it('computes the no-model tooltip when not loaded', () => {
    setup({ model_loaded: false });
    expect(component['tooltip']()).toBe(
      'No hay modelo de predicción cargado en el backend.',
    );
  });

  it('shows the loaded date when present', () => {
    setup({
      model_loaded: true,
      base_version: 'rf-db-v1',
      is_synthetic: false,
      loaded_at: '2026-06-01T12:00:00Z',
    });
    expect(fixture.nativeElement.querySelector('.model-footer__loaded')).not.toBeNull();
  });
});
