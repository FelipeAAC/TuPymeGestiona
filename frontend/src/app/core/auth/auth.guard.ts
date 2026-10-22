import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.me().pipe(
    map(() => true),
    catchError(() => of(router.createUrlTree(['/login']))),
  );
};

export const companyAdminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.me().pipe(
    map((response) => {
      if (response.access_modes.includes('COMPANY_ADMIN')) return true;
      return response.access_modes.includes('CUSTOMER')
        ? router.createUrlTree(['/portal'])
        : router.createUrlTree(['/access-chooser']);
    }),
    catchError(() => of(router.createUrlTree(['/login']))),
  );
};
