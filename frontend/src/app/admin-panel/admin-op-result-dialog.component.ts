import { Component, Inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

export interface AdminOpResultData {
  title: string;
  message: string;
  technicalDetail: string | null;
  success: boolean;
}

@Component({
  selector: 'app-admin-op-result-dialog',
  standalone: true,
  imports: [MatButtonModule, MatDialogModule, MatIconModule, MatTooltipModule],
  template: `
    <h2 mat-dialog-title class="dlg-title-row">
      <span class="dlg-title-start">
        <mat-icon class="dlg-icon" [class.ok]="data.success" [class.err]="!data.success">
          {{ data.success ? 'check_circle' : 'error' }}
        </mat-icon>
        {{ data.title }}
      </span>
      @if (data.technicalDetail) {
        <button
          mat-icon-button
          type="button"
          class="info-btn"
          [matTooltip]="data.technicalDetail"
          matTooltipShowDelay="200"
          matTooltipClass="admin-op-tech-tooltip"
          aria-label="Detalle técnico (pasa el cursor)"
        >
          <mat-icon>info</mat-icon>
        </button>
      }
    </h2>
    <mat-dialog-content class="dlg-body">
      <p class="dlg-msg">{{ data.message }}</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-flat-button mat-dialog-close color="primary">Cerrar</button>
    </mat-dialog-actions>
  `,
  styles: `
    .dlg-title-row {
      margin: 0;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 4px;
      font-size: 1.1rem;
      font-weight: 500;
    }
    .dlg-title-start {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex: 1;
    }
    .dlg-icon.ok {
      color: var(--mat-sys-primary, #1a73e8);
    }
    .dlg-icon.err {
      color: var(--mat-sys-error, #b3261e);
    }
    .info-btn {
      flex-shrink: 0;
    }
    .dlg-body {
      padding-top: 8px !important;
    }
    .dlg-msg {
      margin: 0;
      font-size: 14px;
      line-height: 1.45;
      white-space: pre-wrap;
    }
  `,
})
export class AdminOpResultDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<AdminOpResultDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: AdminOpResultData,
  ) {}
}
