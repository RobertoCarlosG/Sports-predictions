import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { DatePipe, NgClass } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ModelInfoService } from '../../services/model-info.service';

@Component({
  selector: 'app-model-footer',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgClass, DatePipe, MatIconModule, MatTooltipModule],
  templateUrl: './model-footer.component.html',
  styleUrl: './model-footer.component.scss',
})
export class ModelFooterComponent {
  private readonly modelInfo = inject(ModelInfoService);

  protected readonly info = this.modelInfo.info;

  protected readonly tooltip = computed<string>(() => {
    const data = this.info();
    if (!data || !data.model_loaded) {
      return 'No hay modelo de predicción cargado en el backend.';
    }
    const parts = [`Modelo: ${data.model_version ?? data.base_version ?? 'rf-v0'}`];
    if (data.is_synthetic) {
      parts.push('Tipo: sintético (fallback de desarrollo).');
    } else {
      parts.push('Tipo: entrenado contra base de datos.');
    }
    if (data.loaded_at) {
      parts.push(`Cargado: ${data.loaded_at}`);
    }
    return parts.join(' · ');
  });

  protected readonly statusLabel = computed<string>(() => {
    const data = this.info();
    if (!data || !data.model_loaded) {
      return 'Modelo no cargado';
    }
    return data.is_synthetic ? 'Modelo sintético (fallback)' : (data.base_version ?? 'rf-v0');
  });
}
