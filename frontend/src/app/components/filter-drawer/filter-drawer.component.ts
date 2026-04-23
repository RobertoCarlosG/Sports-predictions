import { ChangeDetectionStrategy, Component, Input, ViewChild } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSidenav, MatSidenavModule } from '@angular/material/sidenav';

@Component({
  selector: 'app-filter-drawer',
  standalone: true,
  imports: [MatSidenavModule, MatButtonModule, MatIconModule],
  templateUrl: './filter-drawer.component.html',
  styleUrl: './filter-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FilterDrawerComponent {
  @ViewChild('drawer') drawer?: MatSidenav;

  @Input() drawerTitle = 'Filtros';

  open(): void {
    void this.drawer?.open();
  }

  close(): void {
    void this.drawer?.close();
  }
}
