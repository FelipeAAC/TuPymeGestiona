import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import {
  CatalogCategoryCreateInput,
  CatalogCategoryDetail,
} from '../../core/catalog/catalog.models';
import { CatalogService } from '../../core/catalog/catalog.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

@Component({
  selector: 'app-categories',
  imports: [ReactiveFormsModule],
  templateUrl: './categories.html',
  styleUrl: './categories.scss',
})
export class Categories {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly catalogService = inject(CatalogService);
  private readonly organizationContextService = inject(OrganizationContextService);

  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly categories = signal<CatalogCategoryDetail[]>([]);

  readonly isLoading = signal(false);
  readonly isCreating = signal(false);

  readonly canManageCategories = signal(false);

  readonly errorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly createSuccessMessage = signal('');

  readonly createForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    parentId: [0],
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.categories.set([]);

      this.errorMessage.set('');
      this.createErrorMessage.set('');
      this.createSuccessMessage.set('');

      this.canManageCategories.set(false);
      this.isCreating.set(false);

      this.resetCreateForm();

      if (!membership) {
        this.isLoading.set(false);
        return;
      }

      const companyId = membership.company.id;

      const categoriesSubscription = this.loadCategories(companyId);

      onCleanup(() => {
        categoriesSubscription.unsubscribe();
      });
    });
  }

  onSubmit(): void {
    const membership = this.selectedMembership();

    if (!membership) {
      return;
    }

    if (!this.canManageCategories()) {
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

    const input: CatalogCategoryCreateInput = {
      name,
      parent: formValue.parentId > 0 ? formValue.parentId : null,
    };

    const companyId = membership.company.id;

    this.createErrorMessage.set('');
    this.createSuccessMessage.set('');
    this.isCreating.set(true);

    this.catalogService
      .createCategory(companyId, input)
      .pipe(
        finalize(() => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId === companyId) {
            this.isCreating.set(false);
          }
        }),
      )
      .subscribe({
        next: (category) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.createSuccessMessage.set(`Categoría "${category.name}" creada correctamente.`);

          this.resetCreateForm();
          this.loadCategories(companyId);
        },

        error: (error: HttpErrorResponse) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          if (error.status === 400) {
            this.createErrorMessage.set(
              'No pudimos crear la categoría. Revisa el nombre y la categoría padre.',
            );
            return;
          }

          if (error.status === 403) {
            this.canManageCategories.set(false);
            this.createErrorMessage.set(
              'Ya no tienes permiso para administrar las categorías de esta empresa.',
            );
            return;
          }

          if (error.status === 0) {
            this.createErrorMessage.set(
              'No fue posible conectar con el servidor. Inténtalo nuevamente.',
            );
            return;
          }

          this.createErrorMessage.set('No pudimos crear la categoría. Inténtalo nuevamente.');
        },
      });
  }

  private loadCategories(companyId: number): Subscription {
    this.isLoading.set(true);
    this.errorMessage.set('');

    return this.catalogService
      .listCategories(companyId)
      .pipe(
        finalize(() => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId === companyId) {
            this.isLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (categories) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.categories.set(categories);
          this.canManageCategories.set(true);
        },

        error: (error: HttpErrorResponse) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.categories.set([]);
          this.canManageCategories.set(false);

          if (error.status === 403) {
            this.errorMessage.set(
              'No tienes permiso para administrar las categorías de esta empresa.',
            );
            return;
          }

          if (error.status === 0) {
            this.errorMessage.set('No fue posible conectar con el servidor. Inténtalo nuevamente.');
            return;
          }

          this.errorMessage.set('No pudimos cargar las categorías. Inténtalo nuevamente.');
        },
      });
  }

  private resetCreateForm(): void {
    this.createForm.reset({
      name: '',
      parentId: 0,
    });
  }
}
