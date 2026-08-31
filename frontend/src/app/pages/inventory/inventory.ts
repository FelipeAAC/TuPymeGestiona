import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import {
  FormControl,
  FormGroup,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import {
  InventoryMovement,
  InventoryMovementQuery,
  InventoryMovementType,
  InventoryPermissions,
  InventoryStock,
  InventoryTransfer,
  InventoryVariantOption,
  InventoryWarehouseOption,
} from '../../core/inventory/inventory.models';
import { InventoryService } from '../../core/inventory/inventory.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

type InventoryTab = 'stocks' | 'movements' | 'transfers';
type InventoryEditor = 'movement' | 'transfer';

type TransferItemForm = FormGroup<{
  variantId: FormControl<number>;
  quantity: FormControl<string>;
}>;

const EMPTY_PERMISSIONS: InventoryPermissions = {
  stocks_manage: false,
  movements_manage: false,
  transfers_manage: false,
};

@Component({
  selector: 'app-inventory',
  imports: [DatePipe, DecimalPipe, ReactiveFormsModule],
  templateUrl: './inventory.html',
  styleUrl: './inventory.scss',
})
export class Inventory implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly inventoryService = inject(InventoryService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private optionsSubscription: Subscription | null = null;
  private stocksSubscription: Subscription | null = null;
  private movementsSubscription: Subscription | null = null;
  private transfersSubscription: Subscription | null = null;
  private saveSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly permissions = signal<InventoryPermissions>({ ...EMPTY_PERMISSIONS });
  readonly warehouses = signal<InventoryWarehouseOption[]>([]);
  readonly variants = signal<InventoryVariantOption[]>([]);
  readonly stocks = signal<InventoryStock[]>([]);
  readonly movements = signal<InventoryMovement[]>([]);
  readonly transfers = signal<InventoryTransfer[]>([]);

  readonly activeTab = signal<InventoryTab>('stocks');
  readonly openEditor = signal<InventoryEditor | null>(null);

  readonly isOptionsLoading = signal(false);
  readonly isStocksLoading = signal(false);
  readonly isMovementsLoading = signal(false);
  readonly isTransfersLoading = signal(false);
  readonly isSaving = signal(false);

  readonly optionsErrorMessage = signal('');
  readonly stocksErrorMessage = signal('');
  readonly movementsErrorMessage = signal('');
  readonly transfersErrorMessage = signal('');
  readonly saveErrorMessage = signal('');
  readonly successMessage = signal('');

  readonly appliedStockSearch = signal('');
  readonly appliedStockWarehouse = signal(0);

  readonly stockWarehouses = computed(() =>
    this.warehouses().filter((warehouse) => warehouse.capabilities.stocks),
  );
  readonly movementWarehouses = computed(() =>
    this.warehouses().filter((warehouse) => warehouse.capabilities.movements),
  );
  readonly transferWarehouses = computed(() =>
    this.warehouses().filter((warehouse) => warehouse.capabilities.transfers),
  );
  readonly activeVariants = computed(() =>
    this.variants().filter((variant) => variant.status === 'ACTIVE'),
  );

  readonly visibleStocks = computed(() => {
    const search = this.appliedStockSearch().toLocaleLowerCase();
    const warehouseId = this.appliedStockWarehouse();

    return this.stocks().filter((stock) => {
      if (warehouseId && stock.warehouse !== warehouseId) {
        return false;
      }

      if (!search) {
        return true;
      }

      const warehouse = this.warehouseById(stock.warehouse);
      const variant = this.variantById(stock.variant);
      const searchableText = [
        warehouse?.name,
        warehouse?.code,
        variant?.product_name,
        variant?.sku,
        variant?.gtin,
      ]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase();

      return searchableText.includes(search);
    });
  });

  readonly totalUnits = computed(() =>
    this.stocks().reduce((total, stock) => total + this.quantityAsNumber(stock.quantity), 0),
  );
  readonly stockPositions = computed(() => this.stocks().length);
  readonly stockedWarehouses = computed(
    () => new Set(this.stocks().map((stock) => stock.warehouse)).size,
  );
  readonly emptyPositions = computed(
    () => this.stocks().filter((stock) => this.quantityAsNumber(stock.quantity) === 0).length,
  );

  readonly canCreateMovement = computed(
    () =>
      this.permissions().movements_manage &&
      this.movementWarehouses().length > 0 &&
      this.activeVariants().length > 0,
  );
  readonly canCreateTransfer = computed(
    () =>
      this.permissions().transfers_manage &&
      this.transferWarehouses().length > 1 &&
      this.activeVariants().length > 0,
  );

  readonly stockFilterForm = this.formBuilder.group({
    search: ['', [Validators.maxLength(150)]],
    warehouseId: [0],
  });

  readonly movementFilterForm = this.formBuilder.group({
    warehouseId: [0],
    variantId: [0],
    movementType: this.formBuilder.control<InventoryMovementType | ''>(''),
  });

  readonly movementForm = this.formBuilder.group({
    movementType: this.formBuilder.control<InventoryMovementType>('ENTRY', [Validators.required]),
    warehouseId: [0, [Validators.required, Validators.min(1)]],
    variantId: [0, [Validators.required, Validators.min(1)]],
    quantity: ['', [Validators.required]],
  });

  readonly transferForm = this.formBuilder.group({
    sourceWarehouseId: [0, [Validators.required, Validators.min(1)]],
    destinationWarehouseId: [0, [Validators.required, Validators.min(1)]],
    items: this.formBuilder.array<TransferItemForm>([]),
  });

  readonly transferItems = this.transferForm.controls.items;

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.cancelRequests();
      this.resetPageState();

      if (membership) {
        this.loadOptions(membership.company.id);
      }

      onCleanup(() => this.cancelRequests());
    });
  }

  ngOnDestroy(): void {
    this.cancelRequests();
  }

  selectTab(tab: InventoryTab): void {
    this.activeTab.set(tab);
    this.successMessage.set('');
  }

  applyStockFilters(): void {
    if (this.stockFilterForm.invalid) {
      this.stockFilterForm.markAllAsTouched();
      return;
    }

    const value = this.stockFilterForm.getRawValue();

    this.appliedStockSearch.set(value.search.trim());
    this.appliedStockWarehouse.set(value.warehouseId);
  }

  clearStockFilters(): void {
    this.stockFilterForm.reset({
      search: '',
      warehouseId: 0,
    });
    this.appliedStockSearch.set('');
    this.appliedStockWarehouse.set(0);
  }

  applyMovementFilters(): void {
    const membership = this.selectedMembership();

    if (!membership) {
      return;
    }

    this.loadMovements(membership.company.id, this.currentMovementQuery());
  }

  clearMovementFilters(): void {
    const membership = this.selectedMembership();

    this.movementFilterForm.reset({
      warehouseId: 0,
      variantId: 0,
      movementType: '',
    });

    if (membership) {
      this.loadMovements(membership.company.id, {});
    }
  }

  openMovementEditor(): void {
    if (!this.canCreateMovement()) {
      return;
    }

    this.saveErrorMessage.set('');
    this.movementForm.reset({
      movementType: 'ENTRY',
      warehouseId: this.movementWarehouses()[0]?.id ?? 0,
      variantId: this.activeVariants()[0]?.id ?? 0,
      quantity: '',
    });
    this.openEditor.set('movement');
  }

  openTransferEditor(): void {
    if (!this.canCreateTransfer()) {
      return;
    }

    const warehouses = this.transferWarehouses();

    this.saveErrorMessage.set('');
    this.transferForm.controls.sourceWarehouseId.setValue(warehouses[0]?.id ?? 0);
    this.transferForm.controls.destinationWarehouseId.setValue(warehouses[1]?.id ?? 0);
    this.transferItems.clear();
    this.transferItems.push(this.createTransferItemForm());
    this.openEditor.set('transfer');
  }

  closeEditor(): void {
    if (this.isSaving()) {
      return;
    }

    this.openEditor.set(null);
    this.saveErrorMessage.set('');
  }

  addTransferItem(): void {
    this.transferItems.push(this.createTransferItemForm());
  }

  removeTransferItem(index: number): void {
    if (this.transferItems.length <= 1 || this.isSaving()) {
      return;
    }

    this.transferItems.removeAt(index);
  }

  saveMovement(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canCreateMovement() || this.isSaving()) {
      return;
    }

    if (this.movementForm.invalid) {
      this.movementForm.markAllAsTouched();
      return;
    }

    const value = this.movementForm.getRawValue();
    const normalizedQuantity = this.normalizeQuantity(value.quantity);
    const numericQuantity = Number(normalizedQuantity);

    if (!Number.isFinite(numericQuantity) || numericQuantity === 0) {
      this.movementForm.controls.quantity.setErrors({ invalidQuantity: true });
      this.movementForm.controls.quantity.markAsTouched();
      return;
    }

    if (value.movementType !== 'ADJUSTMENT' && numericQuantity < 0) {
      this.movementForm.controls.quantity.setErrors({ positiveQuantity: true });
      this.movementForm.controls.quantity.markAsTouched();
      return;
    }

    const quantityDelta =
      value.movementType === 'EXIT' ? `-${Math.abs(numericQuantity)}` : normalizedQuantity;
    const companyId = membership.company.id;

    this.beginSave();

    this.saveSubscription = this.inventoryService
      .createMovement(companyId, {
        warehouse: value.warehouseId,
        variant: value.variantId,
        movement_type: value.movementType,
        quantity_delta: quantityDelta,
      })
      .pipe(finalize(() => this.finishSave(companyId)))
      .subscribe({
        next: () => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.openEditor.set(null);
          this.successMessage.set('Movimiento de inventario registrado correctamente.');
          this.loadStocks(companyId);
          this.loadMovements(companyId, this.currentMovementQuery());
        },
        error: (error: HttpErrorResponse) => this.handleSaveError(error, 'movement'),
      });
  }

  saveTransfer(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canCreateTransfer() || this.isSaving()) {
      return;
    }

    if (this.transferForm.invalid) {
      this.transferForm.markAllAsTouched();
      return;
    }

    const value = this.transferForm.getRawValue();

    if (value.sourceWarehouseId === value.destinationWarehouseId) {
      this.transferForm.controls.destinationWarehouseId.setErrors({ sameWarehouse: true });
      this.transferForm.controls.destinationWarehouseId.markAsTouched();
      return;
    }

    const variantIds = value.items.map((item) => item.variantId);

    if (new Set(variantIds).size !== variantIds.length) {
      this.saveErrorMessage.set('Cada variante debe aparecer una sola vez en la transferencia.');
      return;
    }

    const items = value.items.map((item, index) => {
      const quantity = this.normalizeQuantity(item.quantity);
      const numericQuantity = Number(quantity);

      if (!Number.isFinite(numericQuantity) || numericQuantity <= 0) {
        this.transferItems.at(index).controls.quantity.setErrors({ positiveQuantity: true });
      }

      return {
        variant: item.variantId,
        quantity,
      };
    });

    if (this.transferItems.invalid) {
      this.transferItems.markAllAsTouched();
      return;
    }

    const companyId = membership.company.id;

    this.beginSave();

    this.saveSubscription = this.inventoryService
      .createTransfer(companyId, {
        source_warehouse: value.sourceWarehouseId,
        destination_warehouse: value.destinationWarehouseId,
        items,
      })
      .pipe(finalize(() => this.finishSave(companyId)))
      .subscribe({
        next: () => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.openEditor.set(null);
          this.successMessage.set('Transferencia de inventario realizada correctamente.');
          this.loadStocks(companyId);
          this.loadMovements(companyId, this.currentMovementQuery());
          this.loadTransfers(companyId);
        },
        error: (error: HttpErrorResponse) => this.handleSaveError(error, 'transfer'),
      });
  }

  warehouseName(warehouseId: number): string {
    const warehouse = this.warehouseById(warehouseId);

    return warehouse ? warehouse.name : `Bodega #${warehouseId}`;
  }

  warehouseCode(warehouseId: number): string {
    return this.warehouseById(warehouseId)?.code ?? '';
  }

  variantName(variantId: number): string {
    const variant = this.variantById(variantId);

    return variant ? variant.product_name : `Variante #${variantId}`;
  }

  variantSku(variantId: number): string {
    return this.variantById(variantId)?.sku ?? '';
  }

  movementTypeLabel(type: InventoryMovementType): string {
    const labels: Record<InventoryMovementType, string> = {
      ENTRY: 'Entrada',
      EXIT: 'Salida',
      ADJUSTMENT: 'Ajuste',
    };

    return labels[type];
  }

  movementTypeClass(type: InventoryMovementType): string {
    return `movement-${type.toLocaleLowerCase()}`;
  }

  transferStatusLabel(status: string): string {
    return status === 'COMPLETED' ? 'Completada' : 'Cancelada';
  }

  quantityAsNumber(quantity: string): number {
    const value = Number(quantity);

    return Number.isFinite(value) ? value : 0;
  }

  private loadOptions(companyId: number): void {
    this.optionsSubscription?.unsubscribe();
    this.isOptionsLoading.set(true);
    this.optionsErrorMessage.set('');

    this.optionsSubscription = this.inventoryService
      .getOptions(companyId)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isOptionsLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (options) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.permissions.set(options.permissions);
          this.warehouses.set(options.warehouses);
          this.variants.set(options.variants);

          if (options.permissions.stocks_manage) {
            this.loadStocks(companyId);
          }

          if (options.permissions.movements_manage) {
            this.loadMovements(companyId, {});
          }

          if (options.permissions.transfers_manage) {
            this.loadTransfers(companyId);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.optionsErrorMessage.set(this.loadErrorMessage(error, 'el inventario'));
        },
      });
  }

  private loadStocks(companyId: number): void {
    this.stocksSubscription?.unsubscribe();
    this.isStocksLoading.set(true);
    this.stocksErrorMessage.set('');

    this.stocksSubscription = this.inventoryService
      .listStocks(companyId)
      .pipe(finalize(() => this.stopLoading(this.isStocksLoading, companyId)))
      .subscribe({
        next: (stocks) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.stocks.set(stocks);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.stocks.set([]);
            this.stocksErrorMessage.set(this.loadErrorMessage(error, 'las existencias'));
          }
        },
      });
  }

  private loadMovements(companyId: number, query: InventoryMovementQuery): void {
    this.movementsSubscription?.unsubscribe();
    this.isMovementsLoading.set(true);
    this.movementsErrorMessage.set('');

    this.movementsSubscription = this.inventoryService
      .listMovements(companyId, query)
      .pipe(finalize(() => this.stopLoading(this.isMovementsLoading, companyId)))
      .subscribe({
        next: (movements) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.movements.set(movements);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.movements.set([]);
            this.movementsErrorMessage.set(this.loadErrorMessage(error, 'los movimientos'));
          }
        },
      });
  }

  private loadTransfers(companyId: number): void {
    this.transfersSubscription?.unsubscribe();
    this.isTransfersLoading.set(true);
    this.transfersErrorMessage.set('');

    this.transfersSubscription = this.inventoryService
      .listTransfers(companyId)
      .pipe(finalize(() => this.stopLoading(this.isTransfersLoading, companyId)))
      .subscribe({
        next: (transfers) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.transfers.set(transfers);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.transfers.set([]);
            this.transfersErrorMessage.set(this.loadErrorMessage(error, 'las transferencias'));
          }
        },
      });
  }

  private currentMovementQuery(): InventoryMovementQuery {
    const value = this.movementFilterForm.getRawValue();

    return {
      warehouse: value.warehouseId || undefined,
      variant: value.variantId || undefined,
      movement_type: value.movementType || undefined,
    };
  }

  private createTransferItemForm(): TransferItemForm {
    return this.formBuilder.group({
      variantId: [this.activeVariants()[0]?.id ?? 0, [Validators.required, Validators.min(1)]],
      quantity: ['', [Validators.required]],
    });
  }

  private warehouseById(warehouseId: number): InventoryWarehouseOption | undefined {
    return this.warehouses().find((warehouse) => warehouse.id === warehouseId);
  }

  private variantById(variantId: number): InventoryVariantOption | undefined {
    return this.variants().find((variant) => variant.id === variantId);
  }

  private normalizeQuantity(quantity: string): string {
    return quantity.trim().replace(',', '.');
  }

  private beginSave(): void {
    this.saveSubscription?.unsubscribe();
    this.saveErrorMessage.set('');
    this.successMessage.set('');
    this.isSaving.set(true);
  }

  private finishSave(companyId: number): void {
    if (this.selectedMembership()?.company.id === companyId) {
      this.isSaving.set(false);
    }
  }

  private handleSaveError(error: HttpErrorResponse, operation: InventoryEditor): void {
    if (error.status === 400) {
      this.saveErrorMessage.set(
        this.firstApiError(error) ||
          (operation === 'movement'
            ? 'No pudimos registrar el movimiento. Revisa la cantidad y el stock disponible.'
            : 'No pudimos realizar la transferencia. Revisa las bodegas, cantidades y existencias.'),
      );
      return;
    }

    if (error.status === 403) {
      this.saveErrorMessage.set('Ya no tienes permiso para realizar esta operación.');
      return;
    }

    if (error.status === 0) {
      this.saveErrorMessage.set('No fue posible conectar con el servidor. Inténtalo nuevamente.');
      return;
    }

    this.saveErrorMessage.set('No pudimos completar la operación. Inténtalo nuevamente.');
  }

  private firstApiError(error: HttpErrorResponse): string {
    const detail = error.error?.detail;
    const candidates = [
      detail?.quantity_delta,
      detail?.quantity,
      detail?.destination_warehouse,
      detail?.items,
      error.error?.quantity_delta,
      error.error?.quantity,
      error.error?.destination_warehouse,
      error.error?.items,
      detail,
    ];

    for (const candidate of candidates) {
      if (typeof candidate === 'string') {
        return candidate;
      }

      if (Array.isArray(candidate) && typeof candidate[0] === 'string') {
        return candidate[0];
      }
    }

    return '';
  }

  private loadErrorMessage(error: HttpErrorResponse, resource: string): string {
    if (error.status === 403) {
      return `No tienes permiso para consultar ${resource} de esta empresa.`;
    }

    if (error.status === 0) {
      return 'No fue posible conectar con el servidor. Inténtalo nuevamente.';
    }

    return `No pudimos cargar ${resource}. Inténtalo nuevamente.`;
  }

  private stopLoading(loadingSignal: { set(value: boolean): void }, companyId: number): void {
    if (this.selectedMembership()?.company.id === companyId) {
      loadingSignal.set(false);
    }
  }

  private resetPageState(): void {
    this.permissions.set({ ...EMPTY_PERMISSIONS });
    this.warehouses.set([]);
    this.variants.set([]);
    this.stocks.set([]);
    this.movements.set([]);
    this.transfers.set([]);
    this.activeTab.set('stocks');
    this.openEditor.set(null);
    this.isOptionsLoading.set(false);
    this.isStocksLoading.set(false);
    this.isMovementsLoading.set(false);
    this.isTransfersLoading.set(false);
    this.isSaving.set(false);
    this.optionsErrorMessage.set('');
    this.stocksErrorMessage.set('');
    this.movementsErrorMessage.set('');
    this.transfersErrorMessage.set('');
    this.saveErrorMessage.set('');
    this.successMessage.set('');
    this.clearStockFilters();
    this.movementFilterForm.reset({
      warehouseId: 0,
      variantId: 0,
      movementType: '',
    });
    this.transferItems.clear();
  }

  private cancelRequests(): void {
    this.optionsSubscription?.unsubscribe();
    this.stocksSubscription?.unsubscribe();
    this.movementsSubscription?.unsubscribe();
    this.transfersSubscription?.unsubscribe();
    this.saveSubscription?.unsubscribe();
    this.optionsSubscription = null;
    this.stocksSubscription = null;
    this.movementsSubscription = null;
    this.transfersSubscription = null;
    this.saveSubscription = null;
  }
}
