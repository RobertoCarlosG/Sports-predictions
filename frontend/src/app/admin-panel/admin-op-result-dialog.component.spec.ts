import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import {
  AdminOpResultData,
  AdminOpResultDialogComponent,
} from './admin-op-result-dialog.component';

describe('AdminOpResultDialogComponent', () => {
  let fixture: ComponentFixture<AdminOpResultDialogComponent>;
  let component: AdminOpResultDialogComponent;
  let dialogRefSpy: jasmine.SpyObj<MatDialogRef<AdminOpResultDialogComponent>>;

  function setup(data: AdminOpResultData): void {
    dialogRefSpy = jasmine.createSpyObj<MatDialogRef<AdminOpResultDialogComponent>>(
      'MatDialogRef',
      ['close'],
    );

    TestBed.configureTestingModule({
      imports: [AdminOpResultDialogComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: MAT_DIALOG_DATA, useValue: data },
        { provide: MatDialogRef, useValue: dialogRefSpy },
      ],
    });

    fixture = TestBed.createComponent(AdminOpResultDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('creates and exposes the injected data', () => {
    setup({
      title: 'Operación completada',
      message: 'Todo salió bien.',
      technicalDetail: null,
      success: true,
    });
    expect(component).toBeTruthy();
    expect(component.data.title).toBe('Operación completada');
  });

  it('renders the title and message from the injected data', () => {
    setup({
      title: 'Recarga del modelo',
      message: 'El modelo se recargó correctamente.',
      technicalDetail: null,
      success: true,
    });
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Recarga del modelo');
    expect(text).toContain('El modelo se recargó correctamente.');
  });

  it('shows the success icon when success is true', () => {
    setup({
      title: 'OK',
      message: 'Bien',
      technicalDetail: null,
      success: true,
    });
    const icon = fixture.nativeElement.querySelector('mat-icon.dlg-icon');
    expect(icon.classList).toContain('ok');
    expect((icon.textContent as string).trim()).toBe('check_circle');
  });

  it('shows the error icon when success is false', () => {
    setup({
      title: 'Error',
      message: 'Algo falló',
      technicalDetail: null,
      success: false,
    });
    const icon = fixture.nativeElement.querySelector('mat-icon.dlg-icon');
    expect(icon.classList).toContain('err');
    expect((icon.textContent as string).trim()).toBe('error');
  });

  it('hides the technical-detail button when technicalDetail is null', () => {
    setup({
      title: 'Sin detalle',
      message: 'Mensaje',
      technicalDetail: null,
      success: true,
    });
    expect(fixture.nativeElement.querySelector('button.info-btn')).toBeNull();
  });

  it('renders the technical-detail button when technicalDetail is present', () => {
    setup({
      title: 'Con detalle',
      message: 'Mensaje',
      technicalDetail: 'Stack trace: boom',
      success: false,
    });
    expect(fixture.nativeElement.querySelector('button.info-btn')).not.toBeNull();
  });

  it('closes via the mat-dialog-close action button', () => {
    setup({
      title: 'OK',
      message: 'Bien',
      technicalDetail: null,
      success: true,
    });
    const closeBtn: HTMLButtonElement = fixture.nativeElement.querySelector(
      'mat-dialog-actions button',
    );
    closeBtn.click();
    fixture.detectChanges();
    expect(dialogRefSpy.close).toHaveBeenCalled();
  });
});
