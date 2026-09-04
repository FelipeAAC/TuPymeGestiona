import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import {
  CatalogBrand,
  CatalogCategory,
  CatalogProduct,
  CatalogProductCreateInput,
  CatalogProductStatus,
  CatalogProductUpdateInput,
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
  readonly isUpdating = signal(false);
  readonly canManageProducts = signal(false);
  readonly editingProductId = signal<number | null>(null);
  readonly errorMessage = signal('');
  readonly optionsErrorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly createSuccessMessage = signal('');
  readonly updateErrorMessage = signal('');
  readonly updateSuccessMessage = signal('');

  readonly createForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(200)]],
    description: ['', [Validators.maxLength(2000)]],
    imageUrl: ['', [Validators.maxLength(500)]],
    categoryId: [0, [Validators.required, Validators.min(1)]],
    brandId: [0],
    sku: ['', [Validators.required, Validators.maxLength(100)]],
    gtin: ['', [Validators.maxLength(32)]],
    basePrice: ['', [Validators.required]],
  });

  readonly editForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(200)]],
    description: ['', [Validators.maxLength(2000)]],
    imageUrl: ['', [Validators.maxLength(500)]],
    categoryId: [0, [Validators.required, Validators.min(1)]],
    brandId: [0],
    status: ['DRAFT'],
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
      this.updateErrorMessage.set('');
      this.updateSuccessMessage.set('');
      this.canManageProducts.set(false);
      this.isCreating.set(false);
      this.isUpdating.set(false);
      this.closeEditor();
      this.resetCreateForm();
      if (!membership) {
        this.isLoading.set(false);
        this.isOptionsLoading.set(false);
        return;
      }
      const companyId = membership.company.id;
      const productsSubscription = this.loadProducts(companyId);
      const optionsSubscription = this.loadProductOptions(companyId);
      onCleanup(() => { productsSubscription.unsubscribe(); optionsSubscription.unsubscribe(); });
    });
  }

  onSubmit(): void {
    const membership = this.selectedMembership();
    if (!membership || !this.canManageProducts() || this.isCreating()) return;
    if (this.createForm.invalid) { this.createForm.markAllAsTouched(); return; }
    const value = this.createForm.getRawValue();
    const input: CatalogProductCreateInput = {
      name: value.name.trim(),
      description: value.description.trim(),
      image_url: value.imageUrl.trim(),
      category: value.categoryId,
      brand: value.brandId > 0 ? value.brandId : null,
      variant: { sku: value.sku.trim(), gtin: value.gtin.trim(), base_price: value.basePrice },
    };
    const companyId = membership.company.id;
    this.createErrorMessage.set('');
    this.createSuccessMessage.set('');
    this.isCreating.set(true);
    this.catalogService.createProduct(companyId, input)
      .pipe(finalize(() => { if (this.selectedMembership()?.company.id === companyId) this.isCreating.set(false); }))
      .subscribe({
        next: (product) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.createSuccessMessage.set(`Producto "${product.name}" creado correctamente.`);
          this.resetCreateForm();
          this.loadProducts(companyId);
        },
        error: (error: HttpErrorResponse) => this.createErrorMessage.set(this.productError(error, 'crear')),
      });
  }

  openEditor(product: CatalogProduct): void {
    this.editingProductId.set(product.id);
    this.updateErrorMessage.set('');
    this.updateSuccessMessage.set('');
    this.editForm.reset({
      name: product.name,
      description: product.description,
      imageUrl: product.image_url,
      categoryId: product.category.id,
      brandId: product.brand?.id ?? 0,
      status: product.status,
    });
  }

  closeEditor(): void {
    this.editingProductId.set(null);
    this.editForm.reset({ name: '', description: '', imageUrl: '', categoryId: 0, brandId: 0, status: 'DRAFT' });
  }

  saveProduct(): void {
    const membership = this.selectedMembership();
    const productId = this.editingProductId();
    if (!membership || productId === null || this.isUpdating()) return;
    if (this.editForm.invalid) { this.editForm.markAllAsTouched(); return; }
    const value = this.editForm.getRawValue();
    const input: CatalogProductUpdateInput = {
      name: value.name.trim(),
      description: value.description.trim(),
      image_url: value.imageUrl.trim(),
      category: value.categoryId,
      brand: value.brandId > 0 ? value.brandId : null,
      status: value.status as CatalogProductStatus,
    };
    this.runProductUpdate(membership.company.id, productId, input, 'actualizado');
  }

  setProductStatus(product: CatalogProduct, status: CatalogProductStatus): void {
    const membership = this.selectedMembership();
    if (!membership || this.isUpdating()) return;
    const input: CatalogProductUpdateInput = { status };
    this.runProductUpdate(
      membership.company.id, product.id, input, status === 'INACTIVE' ? 'deshabilitado' : 'reactivado',
    );
  }

  private runProductUpdate(companyId: number, productId: number, input: CatalogProductUpdateInput, action: string): void {
    this.updateErrorMessage.set('');
    this.updateSuccessMessage.set('');
    this.isUpdating.set(true);
    this.catalogService.updateProduct(companyId, productId, input)
      .pipe(finalize(() => { if (this.selectedMembership()?.company.id === companyId) this.isUpdating.set(false); }))
      .subscribe({
        next: (product) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.updateSuccessMessage.set(`Producto "${product.name}" ${action} correctamente.`);
          this.closeEditor();
          this.loadProducts(companyId);
        },
        error: (error: HttpErrorResponse) => this.updateErrorMessage.set(this.productError(error, 'actualizar')),
      });
  }

  private loadProducts(companyId: number): Subscription {
    this.isLoading.set(true);
    this.errorMessage.set('');
    return this.catalogService.listProducts(companyId)
      .pipe(finalize(() => { if (this.selectedMembership()?.company.id === companyId) this.isLoading.set(false); }))
      .subscribe({
        next: (products) => { if (this.selectedMembership()?.company.id === companyId) this.products.set(products); },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.products.set([]);
          this.errorMessage.set(error.status === 403 ? 'No tienes permiso para ver los productos de esta empresa.' : 'No pudimos cargar los productos. Inténtalo nuevamente.');
        },
      });
  }

  private loadProductOptions(companyId: number): Subscription {
    this.isOptionsLoading.set(true);
    this.optionsErrorMessage.set('');
    this.canManageProducts.set(false);
    return this.catalogService.getProductOptions(companyId)
      .pipe(finalize(() => { if (this.selectedMembership()?.company.id === companyId) this.isOptionsLoading.set(false); }))
      .subscribe({
        next: (options) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.categories.set(options.categories);
          this.brands.set(options.brands);
          this.canManageProducts.set(true);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) return;
          this.categories.set([]); this.brands.set([]); this.canManageProducts.set(false);
          if (error.status !== 403) this.optionsErrorMessage.set('No pudimos cargar las opciones necesarias para administrar productos.');
        },
      });
  }

  private productError(error: HttpErrorResponse, verb: string): string {
    if (error.status === 400) return `No pudimos ${verb} el producto. Revisa los datos ingresados.`;
    if (error.status === 403) return 'Ya no tienes permiso para administrar los productos.';
    if (error.status === 404) return 'El producto ya no existe en esta empresa.';
    if (error.status === 0) return 'No fue posible conectar con el servidor. Inténtalo nuevamente.';
    return `No pudimos ${verb} el producto. Inténtalo nuevamente.`;
  }

  private resetCreateForm(): void {
    this.createForm.reset({ name: '', description: '', imageUrl: '', categoryId: 0, brandId: 0, sku: '', gtin: '', basePrice: '' });
  }
}
