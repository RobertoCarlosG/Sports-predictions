import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { FeaturesService } from '../services/features.service';

export const nbaFeatureGuard: CanActivateFn = () => {
  const features = inject(FeaturesService);
  const router = inject(Router);
  if (features.nbaEnabled()) {
    return true;
  }
  return router.createUrlTree(['/nba-coming-soon']);
};
