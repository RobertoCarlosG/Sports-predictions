import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';

/**
 * Detección por defecto: con OnPush, las actualizaciones del hijo bajo <router-outlet> (p. ej. señales
 * o HTTP en la lista de partidos) no siempre refrescan la vista hasta otra interacción.
 */
@Component({
  selector: 'app-mlb-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatButtonModule],
  templateUrl: './mlb-layout.component.html',
  styleUrl: './mlb-layout.component.scss',
})
export class MlbLayoutComponent {}
