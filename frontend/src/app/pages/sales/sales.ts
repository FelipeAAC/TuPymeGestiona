import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, forkJoin, Subscription } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import {
  PosSaleCreateRequest,
  Sale,
  SaleEvent,
  SaleEventType,
  SaleListQuery,
  SaleOptionVariant,
  SaleOptionDeliveredOrder,
  SaleOptionsResponse,
  SalePagination,
  SaleStatus,
} from '../../core/sales/sales.models';
import { SalesService } from '../../core/sales/sales.service';

const EMPTY_PAGINATION: SalePagination = {
  count: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
  next_page: null,
  previous_page: null,
};

interface PosCartItem {
  variant: number;
  sku: string;
  name: string;
  unitPrice: number;
  stock: number;
  quantity: number;
}

@Component({
  selector: 'app-sales',
  imports: [ReactiveFormsModule],
  templateUrl: './sales.html',
  styleUrls: ['./sales.scss', './sales-dialogs.scss'],
})
export class Sales implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly salesService = inject(SalesService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private workspaceSubscription: Subscription | null = null;
  private listSubscription: Subscription | null = null;
  private detailSubscription: Subscription | null = null;
  private createSubscription: Subscription | null = null;
  private paymentSubscription: Subscription | null = null;
  private cancelSubscription: Subscription | null = null;
  private posOptionsSubscription: Subscription | null = null;
  private posCreateSubscription: Subscription | null = null;
  private reverseSubscription: Subscription | null = null;
  private createIdempotencyKey = '';
  private paymentIdempotencyKey = '';
  private posIdempotencyKey = '';

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly sales = signal<Sale[]>([]);
  readonly options = signal<SaleOptionsResponse | null>(null);
  readonly posOptions = signal<SaleOptionsResponse | null>(null);
  readonly posItems = signal<PosCartItem[]>([]);
  readonly pagination = signal<SalePagination>({ ...EMPTY_PAGINATION });
  readonly activeFilters = signal<SaleListQuery>({ ordering: '-number', page_size: 20 });

  readonly isLoading = signal(false);
  readonly isDetailLoading = signal(false);
  readonly isCreating = signal(false);
  readonly isPaymentSaving = signal(false);
  readonly isPosLoading = signal(false);
  readonly isPosCreating = signal(false);
  readonly isReversing = signal(false);
  readonly cancellingSaleId = signal<number | null>(null);
  readonly isCreateOpen = signal(false);
  readonly isPaymentOpen = signal(false);
  readonly isPosOpen = signal(false);
  readonly isDetailOpen = signal(false);
  readonly paymentSale = signal<Sale | null>(null);
  readonly detailSale = signal<Sale | null>(null);
  readonly cancelCandidate = signal<Sale | null>(null);
  readonly reverseCandidate = signal<Sale | null>(null);

  readonly listErrorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly paymentErrorMessage = signal('');
  readonly posErrorMessage = signal('');
  readonly reverseErrorMessage = signal('');
  readonly detailErrorMessage = signal('');
  readonly actionErrorMessage = signal('');
  readonly successMessage = signal('');

  readonly canManageSales = computed(() => this.options()?.permissions.manage ?? false);
  readonly pendingCount = computed(
    () => this.sales().filter((sale) => sale.status === 'PENDING').length,
  );
  readonly partialCount = computed(
    () => this.sales().filter((sale) => sale.status === 'PARTIAL').length,
  );
  readonly paidCount = computed(() => this.sales().filter((sale) => sale.status === 'PAID').length);
  readonly visibleBalance = computed(() =>
    this.sales().reduce((total, sale) => total + Number(sale.balance), 0),
  );
  readonly posTotal = computed(() =>
    this.posItems().reduce((total, item) => total + item.quantity * item.unitPrice, 0),
  );
  readonly posItemCount = computed(() =>
    this.posItems().reduce((total, item) => total + item.quantity, 0),
  );

  readonly filterForm = this.formBuilder.group({
    search: ['', [Validators.maxLength(150)]],
    status: this.formBuilder.control<SaleStatus | ''>(''),
    branchId: 0,
    ordering: '-number',
  });

  readonly createForm = this.formBuilder.group({
    orderId: this.formBuilder.control<number | null>(null, [Validators.required]),
  });

  readonly paymentForm = this.formBuilder.group({
    amount: this.formBuilder.control<number | null>(null, [
      Validators.required,
      Validators.min(0.01),
    ]),
    reference: ['', [Validators.required, Validators.maxLength(150)]],
  });

  readonly posForm = this.formBuilder.group({
    branchId: this.formBuilder.control<number | null>(null, [Validators.required]),
    warehouseId: this.formBuilder.control<number | null>(null, [Validators.required]),
    customerId: this.formBuilder.control<number | null>(null),
    variantId: this.formBuilder.control<number | null>(null),
    quantity: this.formBuilder.control<number>(1, [Validators.required, Validators.min(0.001)]),
    paymentMethodId: this.formBuilder.control<number | null>(null, [Validators.required]),
    reference: ['', [Validators.required, Validators.maxLength(150)]],
  });

  readonly reverseForm = this.formBuilder.group({
    reference: ['', [Validators.required, Validators.maxLength(150)]],
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.cancelRequests();
      this.resetWorkspace();

      if (membership) {
        this.loadWorkspace(membership.company.id);
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

    const membership = this.selectedMembership();

    if (!membership) {
      return;
    }

    const value = this.filterForm.getRawValue();
    this.activeFilters.set({
      search: value.search.trim(),
      status: value.status,
      branch: value.branchId || null,
      ordering: value.ordering,
      page_size: 20,
    });
    this.loadSales(membership.company.id, 1);
  }

  clearFilters(): void {
    const membership = this.selectedMembership();

    this.resetFilterForm();
    this.activeFilters.set({ ordering: '-number', page_size: 20 });

    if (membership) {
      this.loadSales(membership.company.id, 1);
    }
  }

  goToPage(page: number | null): void {
    const membership = this.selectedMembership();

    if (!membership || !page || this.isLoading()) {
      return;
    }

    this.loadSales(membership.company.id, page);
  }

  openCreate(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canManageSales() || this.isLoading()) {
      return;
    }

    this.createForm.reset({ orderId: null });
    this.createErrorMessage.set('');
    this.createIdempotencyKey = this.newIdempotencyKey('sale', membership.company.id);
    this.isCreateOpen.set(true);
  }

  closeCreate(): void {
    if (this.isCreating()) {
      return;
    }

    this.isCreateOpen.set(false);
    this.createErrorMessage.set('');
    this.createIdempotencyKey = '';
    this.createForm.reset({ orderId: null });
  }

  selectedDeliveredOrder(): SaleOptionDeliveredOrder | null {
    const orderId = this.createForm.controls.orderId.value;
    return this.options()?.delivered_orders.find((order) => order.id === orderId) ?? null;
  }

  createSale(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canManageSales() || this.isCreating()) {
      return;
    }

    if (this.createForm.invalid || this.createForm.controls.orderId.value === null) {
      this.createForm.markAllAsTouched();
      this.createErrorMessage.set('Selecciona un pedido entregado para crear la venta.');
      return;
    }

    const companyId = membership.company.id;
    const orderId = this.createForm.controls.orderId.value;
    this.createIdempotencyKey ||= this.newIdempotencyKey('sale', companyId);
    this.createSubscription?.unsubscribe();
    this.createErrorMessage.set('');
    this.successMessage.set('');
    this.isCreating.set(true);

    this.createSubscription = this.salesService
      .createSale(companyId, orderId, this.createIdempotencyKey)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isCreating.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.isCreateOpen.set(false);
          this.createForm.reset({ orderId: null });
          this.createIdempotencyKey = '';
          this.successMessage.set(
            response.idempotent_replay
              ? `Venta #${response.sale.number} recuperada sin duplicarla.`
              : `Venta #${response.sale.number} creada desde el pedido #${response.sale.order_number}.`,
          );
          this.loadWorkspace(companyId);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.createErrorMessage.set(this.messageForError(error, 'crear la venta'));
          }
        },
      });
  }

  openPos(): void {
    const membership = this.selectedMembership();
    const currentOptions = this.options();

    if (!membership || !this.canManageSales() || this.isLoading()) {
      return;
    }

    const branchId = currentOptions?.branches[0]?.id ?? membership.branches[0]?.id ?? null;
    const warehouse =
      (currentOptions?.warehouses ?? []).find((candidate) => candidate.branch === branchId) ??
      currentOptions?.warehouses?.[0];
    const paymentMethod = (currentOptions?.payment_methods ?? [])[0];

    this.posOptions.set(currentOptions);
    this.posItems.set([]);
    this.posForm.reset({
      branchId,
      warehouseId: warehouse?.id ?? null,
      customerId: null,
      variantId: null,
      quantity: 1,
      paymentMethodId: paymentMethod?.id ?? null,
      reference: '',
    });
    this.posErrorMessage.set('');
    this.posIdempotencyKey = this.newIdempotencyKey('pos', membership.company.id);
    this.isPosOpen.set(true);

    if (branchId && warehouse?.id) {
      this.loadPosOptions(membership.company.id, branchId, warehouse.id);
    }
  }

  closePos(force = false): void {
    if (this.isPosCreating() && !force) {
      return;
    }

    this.posOptionsSubscription?.unsubscribe();
    this.posOptionsSubscription = null;
    this.isPosOpen.set(false);
    this.isPosLoading.set(false);
    this.posItems.set([]);
    this.posOptions.set(null);
    this.posErrorMessage.set('');
    this.posIdempotencyKey = '';
    this.posForm.reset({
      branchId: null,
      warehouseId: null,
      customerId: null,
      variantId: null,
      quantity: 1,
      paymentMethodId: null,
      reference: '',
    });
  }

  refreshPosOptions(): void {
    const membership = this.selectedMembership();
    const value = this.posForm.getRawValue();

    if (!membership || !value.branchId || !value.warehouseId || this.isPosLoading()) {
      return;
    }

    this.posItems.set([]);
    this.loadPosOptions(membership.company.id, value.branchId, value.warehouseId);
  }

  onPosBranchChange(): void {
    const membership = this.selectedMembership();
    const branchId = this.posForm.controls.branchId.value;
    const warehouses = this.posWarehouses().filter(
      (warehouse) => warehouse.branch === branchId || warehouse.branch === null,
    );
    const warehouseId = warehouses[0]?.id ?? null;
    this.posForm.patchValue({ warehouseId, variantId: null });
    this.posItems.set([]);
    if (membership && branchId && warehouseId) {
      this.loadPosOptions(membership.company.id, branchId, warehouseId);
    }
  }

  posWarehouses() {
    const branchId = this.posForm.controls.branchId.value;
    return (this.posOptions()?.warehouses ?? this.options()?.warehouses ?? []).filter(
      (warehouse) => warehouse.branch === branchId || warehouse.branch === null,
    );
  }

  posPaymentMethods() {
    return this.posOptions()?.payment_methods ?? this.options()?.payment_methods ?? [];
  }

  posCustomers() {
    return this.posOptions()?.customers ?? this.options()?.customers ?? [];
  }

  posVariants() {
    return this.posOptions()?.variants ?? [];
  }

  selectedPosVariant(): SaleOptionVariant | null {
    const variantId = this.posForm.controls.variantId.value;
    return this.posVariants().find((variant) => variant.id === variantId) ?? null;
  }

  addPosItem(): void {
    const variant = this.selectedPosVariant();
    const quantity = this.normalizePosQuantity(
      Number(this.posForm.controls.quantity.value),
    );

    if (!variant || !Number.isFinite(quantity) || quantity <= 0) {
      this.posErrorMessage.set('Selecciona un producto y una cantidad válida.');
      return;
    }

    const currentQuantity =
      this.posItems().find((item) => item.variant === variant.id)?.quantity ?? 0;
    const stock = Number(variant.stock);

    if (currentQuantity + quantity > stock) {
      this.posErrorMessage.set(`La cantidad supera el stock disponible de ${variant.sku}.`);
      return;
    }

    this.posItems.update((items) => {
      const existing = items.find((item) => item.variant === variant.id);
      if (existing) {
        return items.map((item) =>
          item.variant === variant.id
            ? { ...item, quantity: this.normalizePosQuantity(item.quantity + quantity) }
            : item,
        );
      }

      return [
        ...items,
        {
          variant: variant.id,
          sku: variant.sku,
          name: variant.name,
          unitPrice: Number(variant.unit_price),
          stock,
          quantity,
        },
      ];
    });
    this.posErrorMessage.set('');
    this.posForm.patchValue({ variantId: null, quantity: 1 });
  }

  private normalizePosQuantity(value: number): number {
    return Math.round(value * 1000) / 1000;
  }

  removePosItem(variantId: number): void {
    this.posItems.update((items) => items.filter((item) => item.variant !== variantId));
  }

  createPosSale(): void {
    const membership = this.selectedMembership();
    const value = this.posForm.getRawValue();

    if (!membership || !this.canManageSales() || this.isPosCreating()) {
      return;
    }

    if (
      this.posForm.invalid ||
      !value.branchId ||
      !value.warehouseId ||
      !value.paymentMethodId ||
      this.posItems().length === 0
    ) {
      this.posForm.markAllAsTouched();
      this.posErrorMessage.set(
        'Completa sucursal, bodega, medio de pago y agrega al menos un producto.',
      );
      return;
    }

    const companyId = membership.company.id;
    const payload: PosSaleCreateRequest = {
      branch: value.branchId,
      warehouse: value.warehouseId,
      customer: value.customerId ?? null,
      items: this.posItems().map((item) => ({
        variant: item.variant,
        quantity: item.quantity,
        unit_price: item.unitPrice,
      })),
      payment_method: value.paymentMethodId,
      reference: value.reference.trim(),
      idempotency_key: (this.posIdempotencyKey ||= this.newIdempotencyKey('pos', companyId)),
    };

    this.posCreateSubscription?.unsubscribe();
    this.posErrorMessage.set('');
    this.successMessage.set('');
    this.isPosCreating.set(true);

    this.posCreateSubscription = this.salesService
      .createPosSale(companyId, payload)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isPosCreating.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.closePos(true);
          this.updateSaleEverywhere(response.sale);
          this.successMessage.set(
            response.idempotent_replay
              ? `Venta POS #${response.sale.number} recuperada sin duplicarla.`
              : `Venta POS #${response.sale.number} creada y pagada.`,
          );
          this.loadWorkspace(companyId);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.posErrorMessage.set(this.messageForError(error, 'crear la venta POS'));
          }
        },
      });
  }

  openPayment(sale: Sale): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canPay(sale)) {
      return;
    }

    this.paymentSale.set(sale);
    this.paymentForm.reset({ amount: Number(sale.balance), reference: '' });
    this.paymentErrorMessage.set('');
    this.paymentIdempotencyKey = this.newIdempotencyKey('payment', membership.company.id);
    this.isPaymentOpen.set(true);
  }

  closePayment(): void {
    if (this.isPaymentSaving()) {
      return;
    }

    this.isPaymentOpen.set(false);
    this.paymentSale.set(null);
    this.paymentErrorMessage.set('');
    this.paymentIdempotencyKey = '';
    this.paymentForm.reset({ amount: null, reference: '' });
  }

  recordPayment(): void {
    const membership = this.selectedMembership();
    const sale = this.paymentSale();

    if (!membership || !sale || !this.canPay(sale) || this.isPaymentSaving()) {
      return;
    }

    if (this.paymentForm.invalid || this.paymentForm.controls.amount.value === null) {
      this.paymentForm.markAllAsTouched();
      this.paymentErrorMessage.set('Ingresa un monto positivo y una referencia de pago.');
      return;
    }

    const value = this.paymentForm.getRawValue();
    const amount = Number(value.amount);

    if (amount > Number(sale.balance)) {
      this.paymentErrorMessage.set('El pago no puede superar el saldo pendiente de la venta.');
      return;
    }

    const companyId = membership.company.id;
    this.paymentIdempotencyKey ||= this.newIdempotencyKey('payment', companyId);
    this.paymentSubscription?.unsubscribe();
    this.paymentErrorMessage.set('');
    this.successMessage.set('');
    this.isPaymentSaving.set(true);

    this.paymentSubscription = this.salesService
      .recordPayment(companyId, sale.id, amount, value.reference.trim(), this.paymentIdempotencyKey)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isPaymentSaving.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.updateSaleEverywhere(response.sale);
          this.isPaymentOpen.set(false);
          this.paymentSale.set(null);
          this.paymentIdempotencyKey = '';
          this.paymentForm.reset({ amount: null, reference: '' });
          this.successMessage.set(
            response.idempotent_replay
              ? `Pago de la venta #${response.sale.number} recuperado sin duplicarlo.`
              : `Pago de ${this.formatMoney(response.payment.amount)} registrado en la venta #${response.sale.number}.`,
          );
          this.loadSales(companyId, this.pagination().page);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.paymentErrorMessage.set(this.messageForError(error, 'registrar el pago'));
          }
        },
      });
  }

  requestCancel(sale: Sale): void {
    if (this.canCancel(sale)) {
      this.actionErrorMessage.set('');
      this.cancelCandidate.set(sale);
    }
  }

  closeCancelConfirmation(): void {
    if (this.cancellingSaleId() === null) {
      this.cancelCandidate.set(null);
    }
  }

  confirmCancel(): void {
    const membership = this.selectedMembership();
    const sale = this.cancelCandidate();

    if (!membership || !sale || !this.canCancel(sale) || this.cancellingSaleId() !== null) {
      return;
    }

    const companyId = membership.company.id;
    this.cancelSubscription?.unsubscribe();
    this.actionErrorMessage.set('');
    this.successMessage.set('');
    this.cancellingSaleId.set(sale.id);

    this.cancelSubscription = this.salesService
      .cancelSale(companyId, sale.id)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.cancellingSaleId.set(null);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.cancelCandidate.set(null);
          this.updateSaleEverywhere(response.sale);
          this.successMessage.set(
            response.already_cancelled
              ? `La venta #${response.sale.number} ya estaba anulada.`
              : `Venta #${response.sale.number} anulada correctamente.`,
          );
          this.loadSales(companyId, this.pagination().page);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.actionErrorMessage.set(this.messageForError(error, 'anular la venta'));
          }
        },
      });
  }

  requestReverse(sale: Sale): void {
    if (!this.canReverse(sale)) {
      return;
    }

    this.reverseErrorMessage.set('');
    this.reverseForm.reset({ reference: '' });
    this.reverseCandidate.set(sale);
  }

  closeReverseConfirmation(): void {
    if (!this.isReversing()) {
      this.reverseCandidate.set(null);
      this.reverseErrorMessage.set('');
      this.reverseForm.reset({ reference: '' });
    }
  }

  confirmReverse(): void {
    const membership = this.selectedMembership();
    const sale = this.reverseCandidate();

    if (!membership || !sale || !this.canReverse(sale) || this.isReversing()) {
      return;
    }

    if (this.reverseForm.invalid) {
      this.reverseForm.markAllAsTouched();
      this.reverseErrorMessage.set('Ingresa una referencia para dejar trazabilidad de la reversa.');
      return;
    }

    const companyId = membership.company.id;
    const reference = this.reverseForm.controls.reference.value.trim();
    this.reverseSubscription?.unsubscribe();
    this.reverseErrorMessage.set('');
    this.actionErrorMessage.set('');
    this.successMessage.set('');
    this.isReversing.set(true);

    this.reverseSubscription = this.salesService
      .reversePosSale(companyId, sale.id, reference)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isReversing.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.reverseCandidate.set(null);
          this.reverseForm.reset({ reference: '' });
          this.updateSaleEverywhere(response.sale);
          this.successMessage.set(
            response.already_reversed
              ? `La venta POS #${response.sale.number} ya estaba revertida.`
              : `Venta POS #${response.sale.number} revertida correctamente.`,
          );
          this.loadSales(companyId, this.pagination().page);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.reverseErrorMessage.set(this.messageForError(error, 'revertir la venta POS'));
          }
        },
      });
  }

  openDetail(sale: Sale): void {
    const membership = this.selectedMembership();

    if (!membership) {
      return;
    }

    const companyId = membership.company.id;
    this.detailSubscription?.unsubscribe();
    this.detailSale.set(sale);
    this.detailErrorMessage.set('');
    this.isDetailOpen.set(true);
    this.isDetailLoading.set(true);

    this.detailSubscription = this.salesService
      .retrieveSale(companyId, sale.id)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isDetailLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (freshSale) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.detailSale.set(freshSale);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.detailErrorMessage.set(this.messageForError(error, 'cargar el detalle'));
          }
        },
      });
  }

  closeDetail(): void {
    if (this.isPaymentSaving() || this.cancellingSaleId() !== null) {
      return;
    }

    this.detailSubscription?.unsubscribe();
    this.detailSubscription = null;
    this.isDetailOpen.set(false);
    this.isDetailLoading.set(false);
    this.detailSale.set(null);
    this.detailErrorMessage.set('');
  }

  canPay(sale: Sale): boolean {
    return (
      this.canManageSales() &&
      (sale.status === 'PENDING' || sale.status === 'PARTIAL') &&
      Number(sale.balance) > 0
    );
  }

  canCancel(sale: Sale): boolean {
    return this.canManageSales() && sale.status === 'PENDING' && Number(sale.paid_amount) === 0;
  }

  canReverse(sale: Sale): boolean {
    return (
      this.canManageSales() &&
      sale.origin === 'POS' &&
      sale.status === 'PAID' &&
      Number(sale.paid_amount) > 0
    );
  }

  isPosSale(sale: Sale): boolean {
    return sale.origin === 'POS';
  }

  saleOriginLabel(sale: Sale): string {
    return this.isPosSale(sale) ? 'Venta POS' : 'Pedido';
  }

  customerLabel(sale: Sale): string {
    return sale.customer_code && sale.customer_name
      ? `${sale.customer_code} · ${sale.customer_name}`
      : 'Consumidor final';
  }

  warehouseLabel(warehouseId: number | null | undefined): string {
    if (!warehouseId) {
      return 'Sin bodega';
    }

    const warehouse = (this.options()?.warehouses ?? []).find(
      (candidate) => candidate.id === warehouseId,
    );
    return warehouse ? `${warehouse.code} · ${warehouse.name}` : `Bodega ${warehouseId}`;
  }

  statusLabel(status: SaleStatus): string {
    const labels: Record<SaleStatus, string> = {
      PENDING: 'Pendiente',
      PARTIAL: 'Pago parcial',
      PAID: 'Pagada',
      CANCELLED: 'Anulada',
    };

    return labels[status];
  }

  branchLabel(branchId: number): string {
    const branch = this.options()?.branches.find((candidate) => candidate.id === branchId);
    return branch ? `${branch.code} · ${branch.name}` : `Sucursal ${branchId}`;
  }

  eventLabel(eventType: SaleEventType): string {
    const labels: Record<SaleEventType, string> = {
      CREATED: 'Venta creada',
      PAYMENT_RECORDED: 'Pago registrado',
      CANCELLED: 'Venta anulada',
    };

    return labels[eventType];
  }

  eventDescription(event: SaleEvent): string {
    if (event.event_type === 'PAYMENT_RECORDED') {
      return `${this.formatMoney(event.amount ?? 0)} · ${event.reference}`;
    }

    if (event.event_type === 'CANCELLED') {
      if (event.amount !== null && event.amount !== undefined) {
        return `Reversión registrada: ${this.formatMoney(event.amount)} · ${event.reference}`;
      }
      return 'Anulación registrada sin pagos asociados.';
    }

    return `Estado inicial: ${this.statusLabel(event.new_status)}.`;
  }

  formatMoney(value: string | number): string {
    return new Intl.NumberFormat('es-CL', {
      style: 'currency',
      currency: 'CLP',
      maximumFractionDigits: 2,
    }).format(Number(value));
  }

  formatDate(value: string): string {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return new Intl.DateTimeFormat('es-CL', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  }

  private loadPosOptions(companyId: number, branchId: number, warehouseId: number): void {
    this.posOptionsSubscription?.unsubscribe();
    this.isPosLoading.set(true);
    this.posErrorMessage.set('');

    this.posOptionsSubscription = this.salesService
      .getPosOptions(companyId, { branch: branchId, warehouse: warehouseId })
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isPosLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.posOptions.set(response);
            const paymentMethodId = this.posForm.controls.paymentMethodId.value;
            if (!paymentMethodId && response.payment_methods?.length) {
              this.posForm.controls.paymentMethodId.setValue(response.payment_methods[0].id);
            }
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.posOptions.set(null);
            this.posItems.set([]);
            this.posErrorMessage.set(this.messageForError(error, 'cargar las opciones del POS'));
          }
        },
      });
  }

  private loadWorkspace(companyId: number): void {
    this.workspaceSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.listErrorMessage.set('');

    this.workspaceSubscription = forkJoin({
      options: this.salesService.getOptions(companyId),
      list: this.salesService.listSales(companyId, {
        ...this.activeFilters(),
        page: 1,
      }),
    })
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: ({ options, list }) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.options.set(options);
          this.sales.set(list.sales);
          this.pagination.set(list.pagination);

          if (!options.permissions.manage) {
            this.listErrorMessage.set(
              'No tienes permiso para administrar ventas en las sucursales de esta empresa.',
            );
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.sales.set([]);
            this.options.set(null);
            this.pagination.set({ ...EMPTY_PAGINATION });
            this.listErrorMessage.set(this.messageForError(error, 'cargar las ventas'));
          }
        },
      });
  }

  private loadSales(companyId: number, page: number): void {
    this.listSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.listErrorMessage.set('');

    this.listSubscription = this.salesService
      .listSales(companyId, { ...this.activeFilters(), page })
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.sales.set(response.sales);
            this.pagination.set(response.pagination);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.sales.set([]);
            this.pagination.set({ ...EMPTY_PAGINATION, page });
            this.listErrorMessage.set(this.messageForError(error, 'cargar las ventas'));
          }
        },
      });
  }

  private updateSaleEverywhere(updatedSale: Sale): void {
    this.sales.update((sales) =>
      sales.map((sale) => (sale.id === updatedSale.id ? updatedSale : sale)),
    );

    if (this.detailSale()?.id === updatedSale.id) {
      this.detailSale.set(updatedSale);
    }
  }

  private resetWorkspace(): void {
    this.sales.set([]);
    this.options.set(null);
    this.pagination.set({ ...EMPTY_PAGINATION });
    this.activeFilters.set({ ordering: '-number', page_size: 20 });
    this.isLoading.set(false);
    this.isDetailLoading.set(false);
    this.isCreating.set(false);
    this.isPaymentSaving.set(false);
    this.isPosLoading.set(false);
    this.isPosCreating.set(false);
    this.isReversing.set(false);
    this.cancellingSaleId.set(null);
    this.isCreateOpen.set(false);
    this.isPaymentOpen.set(false);
    this.isPosOpen.set(false);
    this.isDetailOpen.set(false);
    this.paymentSale.set(null);
    this.detailSale.set(null);
    this.cancelCandidate.set(null);
    this.reverseCandidate.set(null);
    this.posItems.set([]);
    this.posOptions.set(null);
    this.listErrorMessage.set('');
    this.createErrorMessage.set('');
    this.paymentErrorMessage.set('');
    this.posErrorMessage.set('');
    this.reverseErrorMessage.set('');
    this.detailErrorMessage.set('');
    this.actionErrorMessage.set('');
    this.successMessage.set('');
    this.createIdempotencyKey = '';
    this.paymentIdempotencyKey = '';
    this.posIdempotencyKey = '';
    this.resetFilterForm();
    this.createForm.reset({ orderId: null });
    this.paymentForm.reset({ amount: null, reference: '' });
    this.posForm.reset({
      branchId: null,
      warehouseId: null,
      customerId: null,
      variantId: null,
      quantity: 1,
      paymentMethodId: null,
      reference: '',
    });
    this.reverseForm.reset({ reference: '' });
  }

  private resetFilterForm(): void {
    this.filterForm.reset({
      search: '',
      status: '',
      branchId: 0,
      ordering: '-number',
    });
  }

  private newIdempotencyKey(kind: 'sale' | 'payment' | 'pos', companyId: number): string {
    const randomPart =
      typeof globalThis.crypto?.randomUUID === 'function'
        ? globalThis.crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return `${kind}-${companyId}-${randomPart}`;
  }

  private messageForError(error: HttpErrorResponse, action: string): string {
    const apiMessage = this.firstMessage(error.error);

    if (apiMessage) {
      return apiMessage;
    }

    if (error.status === 0) {
      return 'No fue posible conectar con el servidor. Inténtalo nuevamente.';
    }

    if (error.status === 403) {
      return 'No tienes permiso para realizar esta acción en la empresa o sucursal seleccionada.';
    }

    if (error.status === 404) {
      return 'La venta no existe o quedó fuera de tu alcance autorizado.';
    }

    if (error.status === 409) {
      return 'La venta cambió o su estado actual no permite realizar esta acción.';
    }

    return `No pudimos ${action}. Inténtalo nuevamente.`;
  }

  private firstMessage(value: unknown): string {
    if (typeof value === 'string') {
      return value;
    }

    if (Array.isArray(value)) {
      for (const item of value) {
        const message = this.firstMessage(item);
        if (message) {
          return message;
        }
      }
    }

    if (value && typeof value === 'object') {
      for (const item of Object.values(value as Record<string, unknown>)) {
        const message = this.firstMessage(item);
        if (message) {
          return message;
        }
      }
    }

    return '';
  }

  private cancelRequests(): void {
    this.workspaceSubscription?.unsubscribe();
    this.listSubscription?.unsubscribe();
    this.detailSubscription?.unsubscribe();
    this.createSubscription?.unsubscribe();
    this.paymentSubscription?.unsubscribe();
    this.cancelSubscription?.unsubscribe();
    this.posOptionsSubscription?.unsubscribe();
    this.posCreateSubscription?.unsubscribe();
    this.reverseSubscription?.unsubscribe();
    this.workspaceSubscription = null;
    this.listSubscription = null;
    this.detailSubscription = null;
    this.createSubscription = null;
    this.paymentSubscription = null;
    this.cancelSubscription = null;
    this.posOptionsSubscription = null;
    this.posCreateSubscription = null;
    this.reverseSubscription = null;
  }
}
