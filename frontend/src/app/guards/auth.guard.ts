import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, type CanActivateFn } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { UserAuthService } from '../services/user-auth.service';

export const authGuard: CanActivateFn = (_route: ActivatedRouteSnapshot, state: RouterStateSnapshot) => {
  const auth = inject(UserAuthService);
  const router = inject(Router);

  if (auth.isLoggedIn()) {
    return true;
  }

  return auth.checkSession().pipe(
    map(() => true),
    catchError(() =>
      of(router.createUrlTree(['/login'], { queryParams: { next: state.url } })),
    ),
  );
};
