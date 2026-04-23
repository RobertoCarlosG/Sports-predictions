import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-weather-chip',
  standalone: true,
  imports: [MatIconModule],
  templateUrl: './weather-chip.component.html',
  styleUrl: './weather-chip.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WeatherChipComponent {
  @Input() weather: Record<string, unknown> | null | undefined;

  get tempC(): number | null {
    const w = this.weather;
    if (!w) {
      return null;
    }
    const v = w['temperature_c'];
    return typeof v === 'number' && !Number.isNaN(v) ? v : null;
  }

  get icon(): string {
    const t = this.tempC;
    if (t == null) {
      return 'cloud';
    }
    if (t >= 28) {
      return 'wb_sunny';
    }
    if (t <= 5) {
      return 'ac_unit';
    }
    if (t <= 12) {
      return 'cloud';
    }
    return 'partly_cloudy_day';
  }

  get label(): string | null {
    const t = this.tempC;
    if (t == null) {
      return null;
    }
    return `${Math.round(t)}°C`;
  }
}
