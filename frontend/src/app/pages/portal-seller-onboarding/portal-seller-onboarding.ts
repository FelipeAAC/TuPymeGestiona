import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize, map, switchMap } from 'rxjs';

import { AdministrationService } from '../../core/administration/administration.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

@Component({
  selector: 'app-portal-seller-onboarding',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './portal-seller-onboarding.html',
  styleUrl: './portal-seller-onboarding.scss',
})
export class PortalSellerOnboarding {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly administrationService = inject(AdministrationService);
  private readonly organizationContext = inject(OrganizationContextService);
  private readonly router = inject(Router);

  readonly isSubmitting = signal(false);
  readonly errorMessage = signal('');

  readonly form = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    rut: ['', [Validators.required, Validators.maxLength(20)]],
    legalName: ['', [Validators.required, Validators.maxLength(180)]],
    businessActivity: ['', [Validators.required, Validators.maxLength(180)]],
    contactEmail: ['', [Validators.required, Validators.email]],
    phone: ['', [Validators.maxLength(40)]],
    address: ['', [Validators.required, Validators.maxLength(220)]],
    commune: ['', [Validators.required, Validators.maxLength(120)]],
    city: ['', [Validators.required, Validators.maxLength(120)]],
  });

  submit(): void {
    if (this.form.invalid || this.isSubmitting()) {
      this.form.markAllAsTouched();
      return;
    }

    const value = this.form.getRawValue();
    this.errorMessage.set('');
    this.isSubmitting.set(true);

    this.administrationService
      .createOwnCompany({
        name: value.name.trim(),
        rut: value.rut.trim(),
        legal_name: value.legalName.trim(),
        business_activity: value.businessActivity.trim(),
        contact_email: value.contactEmail.trim(),
        phone: value.phone.trim(),
        address: value.address.trim(),
        commune: value.commune.trim(),
        city: value.city.trim(),
        is_active: true,
      })
      .pipe(
        switchMap((company) =>
          this.organizationContext.load().pipe(
            map((memberships) => ({ company, memberships })),
          ),
        ),
        finalize(() => this.isSubmitting.set(false)),
      )
      .subscribe({
        next: ({ company, memberships }) => {
          const membership = memberships.find((item) => item.company.id === company.id);
          if (membership) {
            this.organizationContext.selectMembership(membership.id);
          }
          void this.router.navigate(['/app/dashboard']);
        },
        error: (error: HttpErrorResponse) => {
          const detail = error.error?.detail;
          const rutError = error.error?.rut;
          this.errorMessage.set(
            typeof detail === 'string'
              ? detail
              : Array.isArray(rutError)
                ? rutError.join(' ')
                : 'No pudimos crear tu PYME. Revisa los datos e inténtalo nuevamente.',
          );
        },
      });
  }
}
