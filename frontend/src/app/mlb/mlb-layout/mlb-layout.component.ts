import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-mlb-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatButtonModule],
  templateUrl: './mlb-layout.component.html',
  styleUrl: './mlb-layout.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MlbLayoutComponent {}
