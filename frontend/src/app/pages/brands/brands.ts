import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import { CatalogBrand, CatalogBrandCreateInput } from '../../core/catalog/catalog.models';
import { CatalogService } from '../../core/catalog/catalog.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

@Component({
  selector: 'app-brands',
  imports: [ReactiveFormsModule],
  templateUrl: './brands.html',
  styleUrl: './brands.scss',
})
export class Brands {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly catalogService = inject(CatalogService);
  private readonly organizationContextService = inject(OrganizationContextService);

  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly brands = signal<CatalogBrand[]>([]);

  readonly isLoading = signal(false);
  readonly isCreating = signal(false);

  readonly canManageBrands = signal(false);

  readonly errorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly createSuccessMessage = signal('');

  readonly createForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.brands.set([]);

      this.errorMessage.set('');
      this.createErrorMessage.set('');
      this.createSuccessMessage.set('');

      this.canManageBrands.set(false);
      this.isCreating.set(false);

      this.resetCreateForm();

      if (!membership) {
        this.isLoading.set(false);
        return;
      }

      const companyId = membership.company.id;

      const brandsSubscription = this.loadBrands(companyId);

      onCleanup(() => {
        brandsSubscription.unsubscribe();
      });
    });
  }

  onSubmit(): void {
    const membership = this.selectedMembership();

    if (!membership) {
      return;
    }

    if (!this.canManageBrands()) {
      return;
    }

    if (this.createForm.invalid) {
      this.createForm.markAllAsTouched();
      return;
    }

    if (this.isCreating()) {
      return;
    }

    const formValue = this.createForm.getRawValue();
    const name = formValue.name.trim();

    if (!name) {
      this.createForm.controls.name.setErrors({
        required: true,
      });
      this.createForm.controls.name.markAsTouched();
      return;
    }

    const input: CatalogBrandCreateInput = {
      name,
    };

    const companyId = membership.company.id;

    this.createErrorMessage.set('');
    this.createSuccessMessage.set('');
    this.isCreating.set(true);

    this.catalogService
      .createBrand(companyId, input)
      .pipe(
        finalize(() => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId === companyId) {
            this.isCreating.set(false);
          }
        }),
      )
      .subscribe({
        next: (brand) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.createSuccessMessage.set(`Marca "${brand.name}" creada correctamente.`);

          this.resetCreateForm();
          this.loadBrands(companyId);
        },

        error: (error: HttpErrorResponse) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          if (error.status === 400) {
            this.createErrorMessage.set('No pudimos crear la marca. Revisa el nombre ingresado.');
            return;
          }

          if (error.status === 403) {
            this.canManageBrands.set(false);
            this.createErrorMessage.set(
              'Ya no tienes permiso para administrar las marcas de esta empresa.',
            );
            return;
          }

          if (error.status === 0) {
            this.createErrorMessage.set(
              'No fue posible conectar con el servidor. Inténtalo nuevamente.',
            );
            return;
          }

          this.createErrorMessage.set('No pudimos crear la marca. Inténtalo nuevamente.');
        },
      });
  }

  private loadBrands(companyId: number): Subscription {
    this.isLoading.set(true);
    this.errorMessage.set('');

    return this.catalogService
      .listBrands(companyId)
      .pipe(
        finalize(() => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId === companyId) {
            this.isLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (brands) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.brands.set(brands);
          this.canManageBrands.set(true);
        },

        error: (error: HttpErrorResponse) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.brands.set([]);
          this.canManageBrands.set(false);

          if (error.status === 403) {
            this.errorMessage.set('No tienes permiso para administrar las marcas de esta empresa.');
            return;
          }

          if (error.status === 0) {
            this.errorMessage.set('No fue posible conectar con el servidor. Inténtalo nuevamente.');
            return;
          }

          this.errorMessage.set('No pudimos cargar las marcas. Inténtalo nuevamente.');
        },
      });
  }

  private resetCreateForm(): void {
    this.createForm.reset({
      name: '',
    });
  }
}
