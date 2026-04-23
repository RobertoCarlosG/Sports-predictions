import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-friendly-error-banner',
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  templateUrl: './friendly-error-banner.component.html',
  styleUrl: './friendly-error-banner.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FriendlyErrorBannerComponent {
  @Input() message = 'No pudimos cargar los datos.';
  @Input() retryLabel = 'Intentar de nuevo →';

  @Output() readonly retry = new EventEmitter<void>();
}
