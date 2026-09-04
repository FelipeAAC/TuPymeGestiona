import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import {
  CatalogCategoryCreateInput,
  CatalogCategoryDetail,
  CatalogCategoryStatus,
  CatalogCategoryUpdateInput,
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
  readonly isUpdating = signal(false);
  readonly canManageCategories = signal(false);
  readonly editingCategoryId = signal<number | null>(null);
  readonly errorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly createSuccessMessage = signal('');
  readonly updateErrorMessage = signal('');
  readonly updateSuccessMessage = signal('');

  readonly createForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    parentId: [0],
  });

  readonly editForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    parentId: [0],
    status: ['ACTIVE'],
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();
      this.categories.set([]);
      this.errorMessage.set('');
      this.createErrorMessage.set('');
      this.createSuccessMessage.set('');
      this.updateErrorMessage.set('');
      this.updateSuccessMessage.set('');
      this.canManageCategories.set(false);
      this.isCreating.set(false);
      this.isUpdating.set(false);
      this.closeEditor();
      this.resetCreateForm();

      if (!membership) {
        this.isLoading.set(false);
        return;
      }
      const subscription = this.loadCategories(membership.company.id);
      onCleanup(() => subscription.unsubscribe());
    });
  }

  onSubmit(): void {
    const membership = this.selectedMembership();
    if (!membership || !this.canManageCategories() || this.isCreating()) return;
    if (this.createForm.invalid) {
      this.createForm.markAllAsTouched();
      return;
    }
    const value = this.createForm.getRawValue();
    const name = value.name.trim();
    if (!name) {
      this.createForm.controls.name.setErrors({ required: true });
      return;
    }
    const input: CatalogCategoryCreateInput = {
      name,
      parent: value.parentId > 0 ? value.parentId : null,
    };
    const companyId = membership.company.id;
    this.createErrorMessage.set('');
    this.createSuccessMessage.set('');
    this.isCreating.set(true);
    this.catalogService
      .createCategory(companyId, input)
      .pipe(finalize(() => this.finishCreating(companyId)))
      .subscribe({
        next: (category) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.createSuccessMessage.set(`Categoría "${category.name}" creada correctamente.`);
          this.resetCreateForm();
          this.loadCategories(companyId);
        },
        error: (error: HttpErrorResponse) =>
          this.createErrorMessage.set(this.categoryError(error, 'crear')),
      });
  }

  openEditor(category: CatalogCategoryDetail): void {
    this.editingCategoryId.set(category.id);
    this.updateErrorMessage.set('');
    this.updateSuccessMessage.set('');
    this.editForm.reset({
      name: category.name,
      parentId: category.parent?.id ?? 0,
      status: category.status,
    });
  }

  closeEditor(): void {
    this.editingCategoryId.set(null);
    this.editForm.reset({ name: '', parentId: 0, status: 'ACTIVE' });
  }

  saveCategory(): void {
    const membership = this.selectedMembership();
    const categoryId = this.editingCategoryId();
    if (!membership || categoryId === null || this.isUpdating()) return;
    if (this.editForm.invalid) {
      this.editForm.markAllAsTouched();
      return;
    }
    const value = this.editForm.getRawValue();
    const input: CatalogCategoryUpdateInput = {
      name: value.name.trim(),
      parent: value.parentId > 0 ? value.parentId : null,
      status: value.status as CatalogCategoryStatus,
    };
    this.runCategoryUpdate(membership.company.id, categoryId, input, 'actualizada');
  }

  setCategoryStatus(category: CatalogCategoryDetail, status: CatalogCategoryStatus): void {
    const membership = this.selectedMembership();
    if (!membership || this.isUpdating()) return;
    this.runCategoryUpdate(
      membership.company.id,
      category.id,
      { status },
      status === 'INACTIVE' ? 'deshabilitada' : 'reactivada',
    );
  }

  parentOptions(categoryId: number): CatalogCategoryDetail[] {
    return this.categories().filter(
      (category) => category.id !== categoryId && category.status === 'ACTIVE',
    );
  }

  private runCategoryUpdate(
    companyId: number,
    categoryId: number,
    input: CatalogCategoryUpdateInput,
    action: string,
  ): void {
    this.updateErrorMessage.set('');
    this.updateSuccessMessage.set('');
    this.isUpdating.set(true);
    this.catalogService
      .updateCategory(companyId, categoryId, input)
      .pipe(finalize(() => this.finishUpdating(companyId)))
      .subscribe({
        next: (category) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.updateSuccessMessage.set(`Categoría "${category.name}" ${action} correctamente.`);
          this.closeEditor();
          this.loadCategories(companyId);
        },
        error: (error: HttpErrorResponse) =>
          this.updateErrorMessage.set(this.categoryError(error, 'actualizar')),
      });
  }

  private loadCategories(companyId: number): Subscription {
    this.isLoading.set(true);
    this.errorMessage.set('');
    return this.catalogService
      .listCategories(companyId)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) this.isLoading.set(false);
        }),
      )
      .subscribe({
        next: (categories) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.categories.set(categories);
          this.canManageCategories.set(true);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.categories.set([]);
          this.canManageCategories.set(false);
          this.errorMessage.set(
            error.status === 403
              ? 'No tienes permiso para administrar las categorías de esta empresa.'
              : 'No pudimos cargar las categorías. Inténtalo nuevamente.',
          );
        },
      });
  }

  private categoryError(error: HttpErrorResponse, verb: string): string {
    if (error.status === 400) return `No pudimos ${verb} la categoría. Revisa los datos ingresados.`;
    if (error.status === 403) return 'Ya no tienes permiso para administrar las categorías.';
    if (error.status === 404) return 'La categoría ya no existe en esta empresa.';
    if (error.status === 0) return 'No fue posible conectar con el servidor. Inténtalo nuevamente.';
    return `No pudimos ${verb} la categoría. Inténtalo nuevamente.`;
  }

  private finishCreating(companyId: number): void {
    if (this.selectedMembership()?.company.id === companyId) this.isCreating.set(false);
  }

  private finishUpdating(companyId: number): void {
    if (this.selectedMembership()?.company.id === companyId) this.isUpdating.set(false);
  }

  private resetCreateForm(): void {
    this.createForm.reset({ name: '', parentId: 0 });
  }
}
