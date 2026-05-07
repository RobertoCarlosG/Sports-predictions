import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { ModelInfoService } from '../../services/model-info.service';
import { ModelFooterComponent } from '../model-footer/model-footer.component';
import { SidebarComponent } from '../sidebar/sidebar.component';

/**
 * El shell usa detección por defecto: con OnPush, las actualizaciones asíncronas (p. ej. HttpClient) en
 * componentes cargados bajo <router-outlet> no hacían que este padre se volviera a comprobar, y la vista
 * solo se actualizaba tras un evento de UI (p. ej. focus en un input).
 */
@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [SidebarComponent, RouterOutlet, ModelFooterComponent],
  templateUrl: './main-layout.component.html',
  styleUrl: './main-layout.component.scss',
})
export class MainLayoutComponent implements OnInit {
  private readonly modelInfo = inject(ModelInfoService);

  ngOnInit(): void {
    this.modelInfo.start();
  }
}
