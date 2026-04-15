import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';

@Component({
  selector: 'app-coming-soon',
  standalone: true,
  imports: [MatCardModule, MatButtonModule, RouterLink],
  templateUrl: './coming-soon.component.html',
  styleUrl: './coming-soon.component.scss',
})
export class ComingSoonComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);

  title = 'Próximamente';
  subtitle = 'Estamos preparando esta competición.';

  ngOnInit(): void {
    const data = this.route.snapshot.data as { title?: string; subtitle?: string };
    if (data['title']) {
      this.title = data['title'];
    }
    if (data['subtitle']) {
      this.subtitle = data['subtitle'];
    }
  }
}
