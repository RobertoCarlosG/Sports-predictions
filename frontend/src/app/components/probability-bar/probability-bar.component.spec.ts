import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { ProbabilityBarComponent } from './probability-bar.component';

describe('ProbabilityBarComponent', () => {
  let fixture: ComponentFixture<ProbabilityBarComponent>;
  let component: ProbabilityBarComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProbabilityBarComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(ProbabilityBarComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('shows no-data text when probability is undefined', () => {
    fixture.detectChanges();
    expect(component.pct()).toBeNull();
    expect(component.barWidth()).toBe(0);
    expect(component.toneClass()).toBe('tone-muted');
    expect(fixture.nativeElement.querySelector('.val-muted')?.textContent).toContain(
      'No prediction',
    );
  });

  it('computes pct as a percentage rounded to one decimal', () => {
    fixture.componentRef.setInput('probability', 0.7345);
    fixture.detectChanges();
    expect(component.pct()).toBe(73.5);
    expect(component.barWidth()).toBe(73.5);
  });

  it('clamps probabilities below 0 and above 1', () => {
    fixture.componentRef.setInput('probability', 1.5);
    fixture.detectChanges();
    expect(component.pct()).toBe(100);

    fixture.componentRef.setInput('probability', -0.5);
    fixture.detectChanges();
    expect(component.pct()).toBe(0);
  });

  it('returns null pct for NaN', () => {
    fixture.componentRef.setInput('probability', NaN);
    fixture.detectChanges();
    expect(component.pct()).toBeNull();
  });

  it('assigns tone classes by threshold', () => {
    fixture.componentRef.setInput('probability', 0.7);
    fixture.detectChanges();
    expect(component.toneClass()).toBe('tone-high');

    fixture.componentRef.setInput('probability', 0.5);
    fixture.detectChanges();
    expect(component.toneClass()).toBe('tone-mid');

    fixture.componentRef.setInput('probability', 0.3);
    fixture.detectChanges();
    expect(component.toneClass()).toBe('tone-low');
  });

  it('renders the percentage and applies the fill width', () => {
    fixture.componentRef.setInput('probability', 0.6);
    fixture.detectChanges();
    const val = fixture.nativeElement.querySelector('.val');
    expect(val?.textContent).toContain('60');
    const fill: HTMLElement = fixture.nativeElement.querySelector('.fill');
    expect(fill.style.width).toBe('60%');
    expect(fill.className).toContain('tone-mid');
  });

  it('renders a custom label and no-data text', () => {
    fixture.componentRef.setInput('label', 'Victoria NYY');
    fixture.componentRef.setInput('noDataText', 'Sin datos');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.lbl')?.textContent).toContain('Victoria NYY');
    expect(fixture.nativeElement.querySelector('.val-muted')?.textContent).toContain('Sin datos');
  });
});
