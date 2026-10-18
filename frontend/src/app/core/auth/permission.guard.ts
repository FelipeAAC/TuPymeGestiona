import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { OrganizationContextService } from '../organization/organization-context.service';

export function permissionGuard(...requiredPermissions: string[]): CanActivateFn {
  return () => {
    const organizationContextService = inject(OrganizationContextService);
    const router = inject(Router);
    const memberships = organizationContextService.memberships();

    const context$ = memberships.length
      ? of(memberships)
      : organizationContextService.load();

    return context$.pipe(
      map((loadedMemberships) => {
        const selectedMembership = organizationContextService.selectedMembership();
        const hasRequiredPermission = (permissions: string[] | undefined): boolean =>
          requiredPermissions.some((permission) => permissions?.includes(permission));
        const authorizedMembership = loadedMemberships.find((membership) =>
          hasRequiredPermission(membership.permissions),
        );

        if (
          authorizedMembership &&
          (!selectedMembership || !hasRequiredPermission(selectedMembership.permissions))
        ) {
          organizationContextService.selectMembership(authorizedMembership.id);
        }

        return authorizedMembership
          ? true
          : router.createUrlTree(['/app/dashboard']);
      }),
      catchError(() => of(router.createUrlTree(['/login']))),
    );
  };
}
