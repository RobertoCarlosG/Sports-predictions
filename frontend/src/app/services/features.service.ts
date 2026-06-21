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

  readonly nbaEnabled = signal(true);

  constructor() {
    this.http
      .get<FeaturesResponse>(`${environment.apiUrl}/features`)
      .pipe(catchError(() => of({ nba_enabled: true })))
      .subscribe((f) => this.nbaEnabled.set(f.nba_enabled));
  }
}
