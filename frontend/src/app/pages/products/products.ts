import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import {
  CatalogBrand,
  CatalogCategory,
  CatalogProduct,
  CatalogProductCreateInput,
} from '../../core/catalog/catalog.models';
import { CatalogService } from '../../core/catalog/catalog.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

@Component({
  selector: 'app-products',
  imports: [ReactiveFormsModule],
  templateUrl: './products.html',
  styleUrl: './products.scss',
})
export class Products {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly catalogService = inject(CatalogService);
  private readonly organizationContextService = inject(OrganizationContextService);

  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly products = signal<CatalogProduct[]>([]);
  readonly categories = signal<CatalogCategory[]>([]);
  readonly brands = signal<CatalogBrand[]>([]);

  readonly isLoading = signal(false);
  readonly isOptionsLoading = signal(false);
  readonly isCreating = signal(false);

  readonly canManageProducts = signal(false);

  readonly errorMessage = signal('');
  readonly optionsErrorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly createSuccessMessage = signal('');

  readonly createForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(200)]],
    categoryId: [0, [Validators.required, Validators.min(1)]],
    brandId: [0],
    sku: ['', [Validators.required, Validators.maxLength(100)]],
    gtin: ['', [Validators.maxLength(32)]],
    basePrice: ['', [Validators.required]],
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.products.set([]);
      this.categories.set([]);
      this.brands.set([]);

      this.errorMessage.set('');
      this.optionsErrorMessage.set('');
      this.createErrorMessage.set('');
      this.createSuccessMessage.set('');

      this.canManageProducts.set(false);
      this.isCreating.set(false);

      this.resetCreateForm();

      if (!membership) {
        this.isLoading.set(false);
        this.isOptionsLoading.set(false);
        return;
      }

      const companyId = membership.company.id;

      const productsSubscription = this.loadProducts(companyId);
      const optionsSubscription = this.loadProductOptions(companyId);

      onCleanup(() => {
        productsSubscription.unsubscribe();
        optionsSubscription.unsubscribe();
      });
    });
  }

  onSubmit(): void {
    const membership = this.selectedMembership();

    if (!membership) {
      return;
    }

    if (!this.canManageProducts()) {
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

    const input: CatalogProductCreateInput = {
      name: formValue.name.trim(),
      category: formValue.categoryId,
      brand: formValue.brandId > 0 ? formValue.brandId : null,
      variant: {
        sku: formValue.sku.trim(),
        gtin: formValue.gtin.trim(),
        base_price: formValue.basePrice,
      },
    };

    const companyId = membership.company.id;

    this.createErrorMessage.set('');
    this.createSuccessMessage.set('');
    this.isCreating.set(true);

    this.catalogService
      .createProduct(companyId, input)
      .pipe(
        finalize(() => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId === companyId) {
            this.isCreating.set(false);
          }
        }),
      )
      .subscribe({
        next: (product) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.createSuccessMessage.set(`Producto "${product.name}" creado correctamente.`);

          this.resetCreateForm();
          this.loadProducts(companyId);
        },

        error: (error: HttpErrorResponse) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          if (error.status === 400) {
            this.createErrorMessage.set(
              'No pudimos crear el producto. Revisa los datos y verifica que el SKU no esté en uso.',
            );
            return;
          }

          if (error.status === 403) {
            this.canManageProducts.set(false);
            this.createErrorMessage.set(
              'Ya no tienes permiso para administrar los productos de esta empresa.',
            );
            return;
          }

          if (error.status === 0) {
            this.createErrorMessage.set(
              'No fue posible conectar con el servidor. Inténtalo nuevamente.',
            );
            return;
          }

          this.createErrorMessage.set('No pudimos crear el producto. Inténtalo nuevamente.');
        },
      });
  }

  private loadProducts(companyId: number): Subscription {
    this.isLoading.set(true);
    this.errorMessage.set('');

    return this.catalogService
      .listProducts(companyId)
      .pipe(
        finalize(() => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId === companyId) {
            this.isLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (products) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.products.set(products);
        },

        error: (error: HttpErrorResponse) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.products.set([]);

          if (error.status === 403) {
            this.errorMessage.set('No tienes permiso para ver los productos de esta empresa.');
            return;
          }

          this.errorMessage.set('No pudimos cargar los productos. Inténtalo nuevamente.');
        },
      });
  }

  private loadProductOptions(companyId: number): Subscription {
    this.isOptionsLoading.set(true);
    this.optionsErrorMessage.set('');
    this.canManageProducts.set(false);

    return this.catalogService
      .getProductOptions(companyId)
      .pipe(
        finalize(() => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId === companyId) {
            this.isOptionsLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (options) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.categories.set(options.categories);
          this.brands.set(options.brands);
          this.canManageProducts.set(true);
        },

        error: (error: HttpErrorResponse) => {
          const currentCompanyId = this.selectedMembership()?.company.id;

          if (currentCompanyId !== companyId) {
            return;
          }

          this.categories.set([]);
          this.brands.set([]);
          this.canManageProducts.set(false);

          if (error.status === 403) {
            return;
          }

          this.optionsErrorMessage.set(
            'No pudimos cargar las opciones necesarias para crear productos.',
          );
        },
      });
  }

  private resetCreateForm(): void {
    this.createForm.reset({
      name: '',
      categoryId: 0,
      brandId: 0,
      sku: '',
      gtin: '',
      basePrice: '',
    });
  }
}
