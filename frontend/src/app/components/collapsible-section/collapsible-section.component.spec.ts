import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { CollapsibleSectionComponent } from './collapsible-section.component';

describe('CollapsibleSectionComponent', () => {
  let fixture: ComponentFixture<CollapsibleSectionComponent>;
  let component: CollapsibleSectionComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CollapsibleSectionComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CollapsibleSectionComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('defaults to collapsed with empty title/subtitle', () => {
    expect(component.expanded).toBe(false);
    expect(component.title).toBe('');
    expect(component.subtitle).toBe('');
  });

  it('renders the title in the panel header', () => {
    component.title = 'Estadísticas';
    fixture.detectChanges();
    const titleEl = fixture.nativeElement.querySelector('mat-panel-title');
    expect(titleEl?.textContent).toContain('Estadísticas');
  });

  it('renders the description only when subtitle is set', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('mat-panel-description')).toBeNull();

    // OnPush: actualizar el input vía setInput para que re-renderice.
    fixture.componentRef.setInput('subtitle', 'detalle');
    fixture.detectChanges();
    const desc = fixture.nativeElement.querySelector('mat-panel-description');
    expect(desc?.textContent).toContain('detalle');
  });
});
