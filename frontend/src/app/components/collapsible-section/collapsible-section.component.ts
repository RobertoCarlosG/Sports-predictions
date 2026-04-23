import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { MatExpansionModule } from '@angular/material/expansion';

@Component({
  selector: 'app-collapsible-section',
  standalone: true,
  imports: [MatExpansionModule],
  templateUrl: './collapsible-section.component.html',
  styleUrl: './collapsible-section.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CollapsibleSectionComponent {
  @Input() title = '';
  @Input() subtitle = '';
  /** Por defecto colapsado (plan UI). */
  @Input() expanded = false;
}
