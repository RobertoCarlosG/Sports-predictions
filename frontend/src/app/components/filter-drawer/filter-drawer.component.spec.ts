import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { FilterDrawerComponent } from './filter-drawer.component';

describe('FilterDrawerComponent', () => {
  let fixture: ComponentFixture<FilterDrawerComponent>;
  let component: FilterDrawerComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FilterDrawerComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(FilterDrawerComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('defaults the drawer title to Filtros', () => {
    fixture.detectChanges();
    const titleEl = fixture.nativeElement.querySelector('.drawer-title');
    expect(titleEl?.textContent).toContain('Filtros');
  });

  it('renders a custom drawer title', () => {
    component.drawerTitle = 'Opciones';
    fixture.detectChanges();
    const titleEl = fixture.nativeElement.querySelector('.drawer-title');
    expect(titleEl?.textContent).toContain('Opciones');
  });

  it('opens the drawer via open()', async () => {
    fixture.detectChanges();
    component.open();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(component.drawer?.opened).toBe(true);
  });

  it('closes the drawer via close()', async () => {
    fixture.detectChanges();
    component.open();
    fixture.detectChanges();
    await fixture.whenStable();
    component.close();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(component.drawer?.opened).toBe(false);
  });
});
