import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { catchError, of } from 'rxjs';

import { environment } from '../../environments/environment';

interface FeaturesResponse {
  nba_enabled: boolean;
}

@Injectable({ providedIn: 'root' })
export class FeaturesService {
  private readonly http = inject(HttpClient);

  /** Default false until /api/v1/features responds — avoids flashing NBA as live. */
  readonly nbaEnabled = signal(false);

  constructor() {
    this.http
      .get<FeaturesResponse>(`${environment.apiUrl}/api/v1/features`)
      .pipe(catchError(() => of({ nba_enabled: false })))
      .subscribe((f) => this.nbaEnabled.set(f.nba_enabled));
  }
}
