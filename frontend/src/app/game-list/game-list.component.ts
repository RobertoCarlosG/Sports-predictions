import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import type { GameDetail } from '../models/game';
import { GamesApiService } from '../services/games-api.service';

@Component({
  selector: 'app-game-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './game-list.component.html',
  styleUrl: './game-list.component.scss',
})
export class GameListComponent implements OnInit {
  private readonly api = inject(GamesApiService);

  dateStr = '';
  games: GameDetail[] = [];
  loading = false;
  error: string | null = null;

  ngOnInit(): void {
    const d = new Date();
    this.dateStr = d.toISOString().slice(0, 10);
    void this.load();
  }

  load(): void {
    this.loading = true;
    this.error = null;
    this.api.listGames(this.dateStr, true).subscribe({
      next: (g) => {
        this.games = g;
        this.loading = false;
      },
      error: (e: unknown) => {
        this.loading = false;
        this.error = e instanceof Error ? e.message : 'Request failed';
      },
    });
  }
}
