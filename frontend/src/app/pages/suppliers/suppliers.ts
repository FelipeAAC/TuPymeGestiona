import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import { Supplier, SupplierInput, SupplierStatus } from '../../core/suppliers/suppliers.models';
import { SuppliersService } from '../../core/suppliers/suppliers.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { SupplierEditor } from './supplier-editor/supplier-editor';

@Component({
  selector: 'app-suppliers',
  imports: [ReactiveFormsModule, SupplierEditor],
  templateUrl: './suppliers.html',
  styleUrl: './suppliers.scss',
})
export class Suppliers implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly suppliersService = inject(SuppliersService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private listSubscription: Subscription | null = null;
  private saveSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly suppliers = signal<Supplier[]>([]);
  readonly searchTerm = signal('');
  readonly statusFilter = signal<SupplierStatus | ''>('');
  readonly canManageSuppliers = signal(false);

  readonly isLoading = signal(false);
  readonly isSaving = signal(false);
  readonly isEditorOpen = signal(false);
  readonly editingSupplier = signal<Supplier | null>(null);

  readonly listErrorMessage = signal('');
  readonly saveErrorMessage = signal('');
  readonly successMessage = signal('');

  readonly activeSuppliers = computed(
    () => this.suppliers().filter((supplier) => supplier.status === 'ACTIVE').length,
  );
  readonly inactiveSuppliers = computed(
    () => this.suppliers().filter((supplier) => supplier.status === 'INACTIVE').length,
  );
  readonly filteredSuppliers = computed(() => {
    const search = this.searchTerm().trim().toLocaleLowerCase('es');
    const status = this.statusFilter();

    return this.suppliers().filter((supplier) => {
      const matchesStatus = !status || supplier.status === status;
      const matchesSearch =
        !search ||
        [supplier.name, supplier.contact_name, supplier.email, supplier.phone].some((value) =>
          value.toLocaleLowerCase('es').includes(search),
        );

      return matchesStatus && matchesSearch;
    });
  });

  readonly filterForm = this.formBuilder.group({
    search: ['', [Validators.maxLength(200)]],
    status: this.formBuilder.control<SupplierStatus | ''>(''),
  });

  readonly supplierForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(200)]],
    contactName: ['', [Validators.maxLength(150)]],
    email: ['', [Validators.email, Validators.maxLength(254)]],
    phone: ['', [Validators.maxLength(50)]],
    status: this.formBuilder.control<SupplierStatus>('ACTIVE', [Validators.required]),
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.cancelRequests();
      this.suppliers.set([]);
      this.canManageSuppliers.set(false);
      this.isLoading.set(false);
      this.isSaving.set(false);
      this.listErrorMessage.set('');
      this.saveErrorMessage.set('');
      this.successMessage.set('');
      this.closeEditor();
      this.resetFilters();

      if (membership) {
        this.loadSuppliers(membership.company.id);
      }

      onCleanup(() => this.cancelRequests());
    });
  }

  ngOnDestroy(): void {
    this.cancelRequests();
  }

  applyFilters(): void {
    if (this.filterForm.invalid) {
      this.filterForm.markAllAsTouched();
      return;
    }

    const value = this.filterForm.getRawValue();
    this.searchTerm.set(value.search.trim());
    this.statusFilter.set(value.status);
    this.successMessage.set('');
  }

  clearFilters(): void {
    this.resetFilters();
    this.successMessage.set('');
  }

  openCreateEditor(): void {
    if (!this.canManageSuppliers()) {
      return;
    }

    this.editingSupplier.set(null);
    this.saveErrorMessage.set('');
    this.resetSupplierForm();
    this.isEditorOpen.set(true);
  }

  openEditEditor(supplier: Supplier): void {
    if (!this.canManageSuppliers()) {
      return;
    }

    this.editingSupplier.set(supplier);
    this.saveErrorMessage.set('');
    this.supplierForm.reset({
      name: supplier.name,
      contactName: supplier.contact_name,
      email: supplier.email,
      phone: supplier.phone,
      status: supplier.status,
    });
    this.isEditorOpen.set(true);
  }

  closeEditor(): void {
    if (this.isSaving()) {
      return;
    }

    this.isEditorOpen.set(false);
    this.editingSupplier.set(null);
    this.saveErrorMessage.set('');
    this.resetSupplierForm();
  }

  saveSupplier(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canManageSuppliers() || this.isSaving()) {
      return;
    }

    if (this.supplierForm.invalid) {
      this.supplierForm.markAllAsTouched();
      return;
    }

    const value = this.supplierForm.getRawValue();
    const input: SupplierInput = {
      name: value.name.trim(),
      contact_name: value.contactName.trim(),
      email: value.email.trim(),
      phone: value.phone.trim(),
      status: value.status,
    };

    if (!input.name) {
      this.supplierForm.controls.name.setErrors({ required: true });
      this.supplierForm.controls.name.markAsTouched();
      return;
    }

    const companyId = membership.company.id;
    const editingSupplier = this.editingSupplier();
    const request = editingSupplier
      ? this.suppliersService.updateSupplier(companyId, editingSupplier.id, input)
      : this.suppliersService.createSupplier(companyId, input);

    this.saveSubscription?.unsubscribe();
    this.saveErrorMessage.set('');
    this.successMessage.set('');
    this.isSaving.set(true);

    this.saveSubscription = request
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isSaving.set(false);
          }
        }),
      )
      .subscribe({
        next: (supplier) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.isEditorOpen.set(false);
          this.editingSupplier.set(null);
          this.successMessage.set(
            editingSupplier
              ? `Proveedor "${supplier.name}" actualizado correctamente.`
              : `Proveedor "${supplier.name}" creado correctamente.`,
          );
          this.loadSuppliers(companyId);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.handleSaveError(error);
        },
      });
  }

  supplierInitials(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join('');
  }

  private loadSuppliers(companyId: number): void {
    this.listSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.listErrorMessage.set('');

    this.listSubscription = this.suppliersService
      .listSuppliers(companyId)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.suppliers.set(response.suppliers);
          this.canManageSuppliers.set(true);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.suppliers.set([]);

          if (error.status === 403) {
            this.canManageSuppliers.set(false);
            this.listErrorMessage.set(
              'No tienes permiso para administrar los proveedores de esta empresa.',
            );
            return;
          }

          if (error.status === 0) {
            this.listErrorMessage.set(
              'No fue posible conectar con el servidor. Inténtalo nuevamente.',
            );
            return;
          }

          this.listErrorMessage.set('No pudimos cargar los proveedores. Inténtalo nuevamente.');
        },
      });
  }

  private handleSaveError(error: HttpErrorResponse): void {
    if (error.status === 400) {
      const nameError = this.firstApiError(error, 'name');
      const emailError = this.firstApiError(error, 'email');

      this.saveErrorMessage.set(
        nameError || emailError || 'No pudimos guardar el proveedor. Revisa los datos ingresados.',
      );
      return;
    }

    if (error.status === 403) {
      this.canManageSuppliers.set(false);
      this.saveErrorMessage.set(
        'Ya no tienes permiso para administrar los proveedores de esta empresa.',
      );
      return;
    }

    if (error.status === 404) {
      this.saveErrorMessage.set('El proveedor ya no existe en esta empresa.');
      return;
    }

    if (error.status === 0) {
      this.saveErrorMessage.set('No fue posible conectar con el servidor. Inténtalo nuevamente.');
      return;
    }

    this.saveErrorMessage.set('No pudimos guardar el proveedor. Inténtalo nuevamente.');
  }

  private firstApiError(error: HttpErrorResponse, field: string): string {
    const value = error.error?.[field];

    if (Array.isArray(value) && typeof value[0] === 'string') {
      return value[0];
    }

    if (typeof value === 'string') {
      return value;
    }

    return '';
  }

  private resetFilters(): void {
    this.filterForm.reset({
      search: '',
      status: '',
    });
    this.searchTerm.set('');
    this.statusFilter.set('');
  }

  private resetSupplierForm(): void {
    this.supplierForm.reset({
      name: '',
      contactName: '',
      email: '',
      phone: '',
      status: 'ACTIVE',
    });
  }

  private cancelRequests(): void {
    this.listSubscription?.unsubscribe();
    this.saveSubscription?.unsubscribe();
    this.listSubscription = null;
    this.saveSubscription = null;
  }
}
