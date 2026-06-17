import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { WeatherChipComponent } from './weather-chip.component';

describe('WeatherChipComponent', () => {
  let fixture: ComponentFixture<WeatherChipComponent>;
  let component: WeatherChipComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [WeatherChipComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(WeatherChipComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('returns null tempC and renders nothing without weather', () => {
    fixture.detectChanges();
    expect(component.tempC).toBeNull();
    expect(component.label).toBeNull();
    expect(component.icon).toBe('cloud');
    expect(fixture.nativeElement.querySelector('.chip')).toBeNull();
  });

  it('returns null tempC when temperature is not a number', () => {
    component.weather = { temperature_c: 'hot' };
    expect(component.tempC).toBeNull();
  });

  it('reads numeric temperature and formats label', () => {
    component.weather = { temperature_c: 21.6 };
    expect(component.tempC).toBe(21.6);
    expect(component.label).toBe('22°C');
  });

  it('chooses the icon by temperature band', () => {
    component.weather = { temperature_c: 30 };
    expect(component.icon).toBe('wb_sunny');
    component.weather = { temperature_c: 3 };
    expect(component.icon).toBe('ac_unit');
    component.weather = { temperature_c: 10 };
    expect(component.icon).toBe('cloud');
    component.weather = { temperature_c: 20 };
    expect(component.icon).toBe('partly_cloudy_day');
  });

  it('renders the chip with label and icon when weather is present', () => {
    component.weather = { temperature_c: 30 };
    fixture.detectChanges();
    const chip = fixture.nativeElement.querySelector('.chip');
    expect(chip).toBeTruthy();
    expect(chip.querySelector('.txt')?.textContent).toContain('30°C');
    expect(chip.querySelector('.ico')?.textContent).toContain('wb_sunny');
  });
});
