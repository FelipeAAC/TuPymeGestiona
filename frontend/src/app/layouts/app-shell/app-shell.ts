import { Component, inject, OnInit, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { finalize } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

@Component({
  selector: 'app-app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.scss',
})
export class AppShell implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly organizationContextService = inject(OrganizationContextService);
  private readonly router = inject(Router);

  readonly currentUser = this.authService.currentUser;

  readonly memberships = this.organizationContextService.memberships;
  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly isOrganizationContextLoading = signal(false);
  readonly organizationContextError = signal('');

  readonly isLoggingOut = signal(false);
  readonly logoutError = signal('');

  ngOnInit(): void {
    this.loadOrganizationContext();
  }

  selectCompany(event: Event): void {
    const target = event.target as HTMLSelectElement;
    const membershipId = Number(target.value);

    if (!Number.isInteger(membershipId)) {
      return;
    }

    this.organizationContextService.selectMembership(membershipId);
  }

  logout(): void {
    if (this.isLoggingOut()) {
      return;
    }

    this.logoutError.set('');
    this.isLoggingOut.set(true);

    this.authService
      .logout()
      .pipe(finalize(() => this.isLoggingOut.set(false)))
      .subscribe({
        next: () => {
          this.organizationContextService.clear();
          void this.router.navigate(['/login']);
        },
        error: () => {
          this.logoutError.set('No pudimos cerrar sesión. Inténtalo nuevamente.');
        },
      });
  }

  private loadOrganizationContext(): void {
    this.organizationContextError.set('');
    this.isOrganizationContextLoading.set(true);

    this.organizationContextService
      .load()
      .pipe(finalize(() => this.isOrganizationContextLoading.set(false)))
      .subscribe({
        error: () => {
          this.organizationContextError.set('No pudimos cargar tus empresas.');
        },
      });
  }
}
