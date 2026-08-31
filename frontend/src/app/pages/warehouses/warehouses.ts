import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationBranch } from '../../core/organization/organization.models';
import { Warehouse, WarehouseInput } from '../../core/warehouses/warehouses.models';
import { WarehousesService } from '../../core/warehouses/warehouses.service';
import { WarehouseEditor } from './warehouse-editor/warehouse-editor';

@Component({
  selector: 'app-warehouses',
  imports: [ReactiveFormsModule, WarehouseEditor],
  templateUrl: './warehouses.html',
  styleUrl: './warehouses.scss',
})
export class Warehouses implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly warehousesService = inject(WarehousesService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private listSubscription: Subscription | null = null;
  private saveSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly branches = computed(() => this.selectedMembership()?.branches ?? []);

  readonly warehouses = signal<Warehouse[]>([]);
  readonly searchTerm = signal('');
  readonly branchFilter = signal(0);
  readonly canManageWarehouses = signal(false);

  readonly isLoading = signal(false);
  readonly isSaving = signal(false);
  readonly isEditorOpen = signal(false);
  readonly editingWarehouse = signal<Warehouse | null>(null);

  readonly listErrorMessage = signal('');
  readonly saveErrorMessage = signal('');
  readonly successMessage = signal('');

  readonly assignedWarehouses = computed(
    () => this.warehouses().filter((warehouse) => warehouse.branch !== null).length,
  );
  readonly generalWarehouses = computed(
    () => this.warehouses().filter((warehouse) => warehouse.branch === null).length,
  );
  readonly filteredWarehouses = computed(() => {
    const search = this.searchTerm().trim().toLocaleLowerCase('es');
    const branchId = this.branchFilter();

    return this.warehouses().filter((warehouse) => {
      const branch = this.branchFor(warehouse);
      const matchesBranch =
        branchId === 0 ||
        (branchId === -1 && warehouse.branch === null) ||
        warehouse.branch === branchId;
      const matchesSearch =
        !search ||
        [warehouse.code, warehouse.name, branch?.code ?? '', branch?.name ?? ''].some((value) =>
          value.toLocaleLowerCase('es').includes(search),
        );

      return matchesBranch && matchesSearch;
    });
  });

  readonly filterForm = this.formBuilder.group({
    search: ['', [Validators.maxLength(200)]],
    branchId: 0,
  });

  readonly warehouseForm = this.formBuilder.group({
    code: ['', [Validators.required, Validators.maxLength(50)]],
    name: ['', [Validators.required, Validators.maxLength(150)]],
    branchId: this.formBuilder.control<number | null>(null),
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.cancelRequests();
      this.warehouses.set([]);
      this.canManageWarehouses.set(false);
      this.isLoading.set(false);
      this.isSaving.set(false);
      this.listErrorMessage.set('');
      this.saveErrorMessage.set('');
      this.successMessage.set('');
      this.closeEditor();
      this.resetFilters();

      if (membership) {
        this.loadWarehouses(membership.company.id);
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
    this.branchFilter.set(value.branchId);
    this.successMessage.set('');
  }

  clearFilters(): void {
    this.resetFilters();
    this.successMessage.set('');
  }

  openCreateEditor(): void {
    if (!this.canManageWarehouses()) {
      return;
    }

    this.editingWarehouse.set(null);
    this.saveErrorMessage.set('');
    this.resetWarehouseForm();
    this.isEditorOpen.set(true);
  }

  openEditEditor(warehouse: Warehouse): void {
    if (!this.canManageWarehouses()) {
      return;
    }

    this.editingWarehouse.set(warehouse);
    this.saveErrorMessage.set('');
    this.warehouseForm.reset({
      code: warehouse.code,
      name: warehouse.name,
      branchId: warehouse.branch,
    });
    this.isEditorOpen.set(true);
  }

  closeEditor(): void {
    if (this.isSaving()) {
      return;
    }

    this.isEditorOpen.set(false);
    this.editingWarehouse.set(null);
    this.saveErrorMessage.set('');
    this.resetWarehouseForm();
  }

  saveWarehouse(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canManageWarehouses() || this.isSaving()) {
      return;
    }

    if (this.warehouseForm.invalid) {
      this.warehouseForm.markAllAsTouched();
      return;
    }

    const value = this.warehouseForm.getRawValue();
    const input: WarehouseInput = {
      branch: value.branchId,
      code: value.code.trim(),
      name: value.name.trim(),
    };

    if (!input.code || !input.name) {
      if (!input.code) {
        this.warehouseForm.controls.code.setErrors({ required: true });
        this.warehouseForm.controls.code.markAsTouched();
      }

      if (!input.name) {
        this.warehouseForm.controls.name.setErrors({ required: true });
        this.warehouseForm.controls.name.markAsTouched();
      }

      return;
    }

    const companyId = membership.company.id;
    const editingWarehouse = this.editingWarehouse();
    const request = editingWarehouse
      ? this.warehousesService.updateWarehouse(companyId, editingWarehouse.id, input)
      : this.warehousesService.createWarehouse(companyId, input);

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
        next: (warehouse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.isEditorOpen.set(false);
          this.editingWarehouse.set(null);
          this.successMessage.set(
            editingWarehouse
              ? `Bodega "${warehouse.name}" actualizada correctamente.`
              : `Bodega "${warehouse.name}" creada correctamente.`,
          );
          this.loadWarehouses(companyId);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.handleSaveError(error);
        },
      });
  }

  warehouseInitials(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join('');
  }

  branchFor(warehouse: Warehouse): OrganizationBranch | undefined {
    return this.branches().find((branch) => branch.id === warehouse.branch);
  }

  private loadWarehouses(companyId: number): void {
    this.listSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.listErrorMessage.set('');

    this.listSubscription = this.warehousesService
      .listWarehouses(companyId)
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

          this.warehouses.set(response.warehouses);
          this.canManageWarehouses.set(true);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.warehouses.set([]);

          if (error.status === 403) {
            this.canManageWarehouses.set(false);
            this.listErrorMessage.set(
              'No tienes permiso para administrar las bodegas de esta empresa.',
            );
            return;
          }

          if (error.status === 0) {
            this.listErrorMessage.set(
              'No fue posible conectar con el servidor. Inténtalo nuevamente.',
            );
            return;
          }

          this.listErrorMessage.set('No pudimos cargar las bodegas. Inténtalo nuevamente.');
        },
      });
  }

  private handleSaveError(error: HttpErrorResponse): void {
    if (error.status === 400) {
      const codeError = this.firstApiError(error, 'code');
      const nameError = this.firstApiError(error, 'name');
      const branchError = this.firstApiError(error, 'branch');
      const formError = this.firstApiError(error, 'non_field_errors');
      const detailError = this.firstApiError(error, 'detail');

      this.saveErrorMessage.set(
        codeError ||
          nameError ||
          branchError ||
          formError ||
          detailError ||
          'No pudimos guardar la bodega. Revisa los datos ingresados.',
      );
      return;
    }

    if (error.status === 403) {
      this.canManageWarehouses.set(false);
      this.saveErrorMessage.set(
        'Ya no tienes permiso para administrar las bodegas de esta empresa o sucursal.',
      );
      return;
    }

    if (error.status === 404) {
      this.saveErrorMessage.set('La bodega ya no existe o no está disponible para esta empresa.');
      return;
    }

    if (error.status === 0) {
      this.saveErrorMessage.set('No fue posible conectar con el servidor. Inténtalo nuevamente.');
      return;
    }

    this.saveErrorMessage.set('No pudimos guardar la bodega. Inténtalo nuevamente.');
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
      branchId: 0,
    });
    this.searchTerm.set('');
    this.branchFilter.set(0);
  }

  private resetWarehouseForm(): void {
    this.warehouseForm.reset({
      code: '',
      name: '',
      branchId: null,
    });
  }

  private cancelRequests(): void {
    this.listSubscription?.unsubscribe();
    this.saveSubscription?.unsubscribe();
    this.listSubscription = null;
    this.saveSubscription = null;
  }
}
