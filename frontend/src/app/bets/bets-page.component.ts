import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';

import {
  BetBankOut,
  BetOut,
  BetPeriodOut,
  BetPeriodStatsOut,
  BetsApiService,
  BetsStatsOut,
} from '../services/bets-api.service';
import { UserAuthService } from '../services/user-auth.service';

@Component({
  selector: 'app-bets-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatDividerModule,
    MatExpansionModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    MatSnackBarModule,
    MatTableModule,
    RouterLink,
  ],
  templateUrl: './bets-page.component.html',
  styleUrl: './bets-page.component.scss',
})
export class BetsPageComponent implements OnInit {
  private readonly userAuth = inject(UserAuthService);
  private readonly betsApi = inject(BetsApiService);
  private readonly snack = inject(MatSnackBar);

  readonly loading = signal(true);
  readonly authReady = signal(false);
  readonly authDetail = signal<string | null>(null);
  readonly session = signal<{ email: string; display_name?: string | null } | null>(null);

  banks = signal<BetBankOut[]>([]);
  selectedBankId = signal<number | null>(null);
  periods = signal<BetPeriodOut[]>([]);
  selectedPeriodId = signal<number | null>(null);
  periodStats = signal<BetPeriodStatsOut | null>(null);
  globalStats = signal<BetsStatsOut | null>(null);
  bets = signal<BetOut[]>([]);

  newBankName = '';
  newBankAmount: number | null = null;

  newBetGamePk: number | null = null;
  newBetType: 'moneyline' | 'over_under' = 'moneyline';
  newBetSideMl: 'home' | 'away' = 'home';
  newBetSideOu: 'over' | 'under' = 'over';
  newBetStake: number | null = null;
  newBetOdds: number | null = null;
  newBetOuLine: number | null = null;

  displayedColumns = ['partido', 'tipo', 'importe', 'estado', 'acciones'];

  ngOnInit(): void {
    this.userAuth.authReady().subscribe({
      next: (r) => {
        this.authReady.set(r.login_available);
        this.authDetail.set(r.detail ?? null);
        if (!r.login_available) {
          this.loading.set(false);
          return;
        }
        this.userAuth.checkSession().subscribe({
          next: (s) => {
            this.session.set({ email: s.email, display_name: s.display_name });
            this.reloadAll();
          },
          error: () => {
            this.session.set(null);
            this.loading.set(false);
          },
        });
      },
      error: () => {
        this.authReady.set(false);
        this.loading.set(false);
      },
    });
  }

  login(): void {
    this.userAuth.startGoogleLogin();
  }

  logout(): void {
    this.userAuth.logout().subscribe({
      next: () => {
        this.session.set(null);
        this.snack.open('Sesión cerrada', 'OK', { duration: 2500 });
      },
      error: () => {
        this.userAuth.clearSessionLocal();
        this.session.set(null);
      },
    });
  }

  reloadAll(): void {
    this.betsApi.listBanks().subscribe({
      next: (b) => {
        this.banks.set(b);
        const sel = this.selectedBankId();
        if (!sel && b.length) {
          this.selectedBankId.set(b[0].id);
        }
        this.refreshPeriodsAndBets();
        this.loading.set(false);
      },
      error: () => {
        this.snack.open('No pudimos cargar los bancos. Reintenta.', 'Cerrar', { duration: 4000 });
        this.loading.set(false);
      },
    });
  }

  refreshPeriodsAndBets(): void {
    const bid = this.selectedBankId();
    if (bid == null) {
      this.periods.set([]);
      this.bets.set([]);
      this.globalStats.set(null);
      return;
    }
    this.betsApi.listPeriods(bid).subscribe({
      next: (p) => {
        this.periods.set(p);
        const pid = this.selectedPeriodId();
        const exists = pid != null && p.some((x) => x.id === pid);
        if (!exists && p.length) {
          this.selectedPeriodId.set(p[0].id);
        }
        this.loadStatsForSelection();
      },
      error: () => this.snack.open('No pudimos cargar los periodos.', 'Cerrar', { duration: 3500 }),
    });
    this.betsApi.listBets({ bank_id: bid }).subscribe({
      next: (rows) => this.bets.set(rows),
      error: () => this.snack.open('No pudimos cargar las apuestas.', 'Cerrar', { duration: 3500 }),
    });
    this.betsApi.globalStats(bid).subscribe({
      next: (s) => this.globalStats.set(s),
      error: () => {},
    });
  }

  onBankChange(id: number): void {
    this.selectedBankId.set(id);
    this.selectedPeriodId.set(null);
    this.periodStats.set(null);
    this.refreshPeriodsAndBets();
  }

  onPeriodChip(pid: number): void {
    this.selectedPeriodId.set(pid);
    this.loadStatsForSelection();
    const bid = this.selectedBankId();
    if (bid != null) {
      this.betsApi.listBets({ bank_id: bid, period_id: pid }).subscribe({
        next: (rows) => this.bets.set(rows),
      });
    }
  }

  loadStatsForSelection(): void {
    const pid = this.selectedPeriodId();
    if (pid == null) {
      this.periodStats.set(null);
      return;
    }
    this.betsApi.periodStats(pid).subscribe({
      next: (s) => this.periodStats.set(s),
      error: () => this.periodStats.set(null),
    });
  }

  createBank(): void {
    const n = this.newBankName.trim();
    const a = this.newBankAmount;
    if (!n || a == null || a <= 0) {
      this.snack.open('Indica nombre e importe inicial válidos.', 'OK', { duration: 3000 });
      return;
    }
    this.betsApi.createBank({ name: n, initial_amount: a }).subscribe({
      next: () => {
        this.newBankName = '';
        this.newBankAmount = null;
        this.reloadAll();
        this.snack.open('Banco creado', 'OK', { duration: 2000 });
      },
      error: () => this.snack.open('No se pudo crear el banco.', 'Cerrar', { duration: 4000 }),
    });
  }

  closePeriod(): void {
    const pid = this.selectedPeriodId();
    if (pid == null) return;
    this.betsApi.closePeriod(pid).subscribe({
      next: () => {
        this.refreshPeriodsAndBets();
        this.snack.open('Periodo cerrado', 'OK', { duration: 2500 });
      },
      error: () => this.snack.open('No se pudo cerrar el periodo.', 'Cerrar', { duration: 4000 }),
    });
  }

  exportPeriod(): void {
    const pid = this.selectedPeriodId();
    if (pid == null) return;
    this.betsApi.exportPeriod(pid).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `apuestas-periodo-${pid}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
      },
      error: () => this.snack.open('No se pudo exportar. Reintenta.', 'Cerrar', { duration: 4000 }),
    });
  }

  submitBet(): void {
    const bid = this.selectedBankId();
    const pk = this.newBetGamePk;
    const stake = this.newBetStake;
    const odds = this.newBetOdds;
    if (bid == null || pk == null || stake == null || odds == null) {
      this.snack.open('Completa banco, número de partido, importe y cuota.', 'OK', { duration: 3500 });
      return;
    }
    const body = {
      bank_id: bid,
      game_pk: pk,
      bet_type: this.newBetType,
      bet_side: this.newBetType === 'moneyline' ? this.newBetSideMl : this.newBetSideOu,
      stake,
      odds,
      ou_line: this.newBetType === 'over_under' ? this.newBetOuLine : null,
    };
    if (body.bet_type === 'over_under' && (body.ou_line == null || Number.isNaN(body.ou_line))) {
      this.snack.open('La apuesta más/menos necesita una línea numérica.', 'OK', { duration: 3500 });
      return;
    }
    this.betsApi.createBet(body).subscribe({
      next: () => {
        this.newBetGamePk = null;
        this.newBetStake = null;
        this.newBetOdds = null;
        this.newBetOuLine = null;
        this.refreshPeriodsAndBets();
        this.snack.open('Apuesta registrada', 'OK', { duration: 2000 });
      },
      error: () => this.snack.open('No se pudo registrar la apuesta.', 'Cerrar', { duration: 4000 }),
    });
  }

  resolve(b: BetOut): void {
    this.betsApi.resolveBet(b.id).subscribe({
      next: () => {
        this.refreshPeriodsAndBets();
        this.snack.open('Resultado actualizado', 'OK', { duration: 2000 });
      },
      error: () => this.snack.open('Aún no hay resultado o hubo un error.', 'Cerrar', { duration: 4000 }),
    });
  }

  roiBarPct(): number {
    const s = this.globalStats();
    if (!s || s.roi_pct == null) return 0;
    return Math.min(100, Math.max(0, (s.roi_pct + 50) / 2));
  }

  statusLabel(st: string): string {
    const m: Record<string, string> = {
      pending: 'Pendiente',
      won: 'Ganada',
      lost: 'Perdida',
      push: 'Empate',
      cancelled: 'Cancelada',
    };
    return m[st] ?? st;
  }

  betTypeLabel(t: string): string {
    return t === 'moneyline' ? 'Ganador' : 'Más/menos';
  }
}
