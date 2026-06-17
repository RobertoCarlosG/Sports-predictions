import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import {
  buildDateSelectionForPreset,
  DateChipSelection,
  DateChipSelectorComponent,
} from './date-chip-selector.component';

function todayIso(): string {
  const t = new Date();
  const y = t.getFullYear();
  const m = String(t.getMonth() + 1).padStart(2, '0');
  const d = String(t.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

describe('buildDateSelectionForPreset', () => {
  it('returns today as a single date', () => {
    const sel = buildDateSelectionForPreset('today', '2020-01-01', '2099-12-31');
    expect(sel.preset).toBe('today');
    expect(sel.dates).toEqual([todayIso()]);
  });

  it('returns tomorrow as a single date one day after today', () => {
    const sel = buildDateSelectionForPreset('tomorrow', '2020-01-01', '2099-12-31');
    expect(sel.preset).toBe('tomorrow');
    expect(sel.dates.length).toBe(1);
    expect(sel.dates[0]).not.toBe(todayIso());
  });

  it('returns a week range (multiple dates)', () => {
    const sel = buildDateSelectionForPreset('week', '2020-01-01', '2099-12-31');
    expect(sel.preset).toBe('week');
    expect(sel.dates.length).toBeGreaterThan(0);
  });
});

describe('DateChipSelectorComponent', () => {
  let fixture: ComponentFixture<DateChipSelectorComponent>;
  let component: DateChipSelectorComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DateChipSelectorComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(DateChipSelectorComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('emits a today selection on init', () => {
    const emitted: DateChipSelection[] = [];
    component.selectionChange.subscribe((s) => emitted.push(s));
    fixture.detectChanges();
    expect(emitted.length).toBe(1);
    expect(emitted[0].preset).toBe('today');
    expect(component.preset()).toBe('today');
  });

  it('fills bounds from current season when not provided', () => {
    fixture.detectChanges();
    expect(component.minIso).toBeTruthy();
    expect(component.maxIso).toBeTruthy();
  });

  it('keeps explicit bounds when provided', () => {
    component.minIso = '2024-04-01';
    component.maxIso = '2024-10-01';
    fixture.detectChanges();
    expect(component.minIso).toBe('2024-04-01');
    expect(component.maxIso).toBe('2024-10-01');
  });

  it('emits a new selection when a chip is selected', () => {
    fixture.detectChanges();
    const emitted: DateChipSelection[] = [];
    component.selectionChange.subscribe((s) => emitted.push(s));
    component.select('week');
    expect(component.preset()).toBe('week');
    expect(emitted.length).toBe(1);
    expect(emitted[0].preset).toBe('week');
  });

  it('renders three chip buttons', () => {
    fixture.detectChanges();
    const buttons = fixture.nativeElement.querySelectorAll('button.chip');
    expect(buttons.length).toBe(3);
  });

  it('marks the active chip with chip-on', () => {
    fixture.detectChanges();
    component.select('tomorrow');
    fixture.detectChanges();
    const active = fixture.nativeElement.querySelector('button.chip-on');
    expect(active?.textContent).toContain('Mañana');
  });
});
