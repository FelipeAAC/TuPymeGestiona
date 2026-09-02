import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, forkJoin, Subscription } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import {
  Sale,
  SaleEvent,
  SaleEventType,
  SaleListQuery,
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
  private createIdempotencyKey = '';
  private paymentIdempotencyKey = '';

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly sales = signal<Sale[]>([]);
  readonly options = signal<SaleOptionsResponse | null>(null);
  readonly pagination = signal<SalePagination>({ ...EMPTY_PAGINATION });
  readonly activeFilters = signal<SaleListQuery>({ ordering: '-number', page_size: 20 });

  readonly isLoading = signal(false);
  readonly isDetailLoading = signal(false);
  readonly isCreating = signal(false);
  readonly isPaymentSaving = signal(false);
  readonly cancellingSaleId = signal<number | null>(null);
  readonly isCreateOpen = signal(false);
  readonly isPaymentOpen = signal(false);
  readonly isDetailOpen = signal(false);
  readonly paymentSale = signal<Sale | null>(null);
  readonly detailSale = signal<Sale | null>(null);
  readonly cancelCandidate = signal<Sale | null>(null);

  readonly listErrorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly paymentErrorMessage = signal('');
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
    this.cancellingSaleId.set(null);
    this.isCreateOpen.set(false);
    this.isPaymentOpen.set(false);
    this.isDetailOpen.set(false);
    this.paymentSale.set(null);
    this.detailSale.set(null);
    this.cancelCandidate.set(null);
    this.listErrorMessage.set('');
    this.createErrorMessage.set('');
    this.paymentErrorMessage.set('');
    this.detailErrorMessage.set('');
    this.actionErrorMessage.set('');
    this.successMessage.set('');
    this.createIdempotencyKey = '';
    this.paymentIdempotencyKey = '';
    this.resetFilterForm();
    this.createForm.reset({ orderId: null });
    this.paymentForm.reset({ amount: null, reference: '' });
  }

  private resetFilterForm(): void {
    this.filterForm.reset({
      search: '',
      status: '',
      branchId: 0,
      ordering: '-number',
    });
  }

  private newIdempotencyKey(kind: 'sale' | 'payment', companyId: number): string {
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
    this.workspaceSubscription = null;
    this.listSubscription = null;
    this.detailSubscription = null;
    this.createSubscription = null;
    this.paymentSubscription = null;
    this.cancelSubscription = null;
  }
}
