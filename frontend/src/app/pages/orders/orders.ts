import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, forkJoin, Observable, Subscription } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import {
  Order,
  OrderInput,
  OrderItem,
  OrderListQuery,
  OrderOptionsResponse,
  OrderPagination,
  OrderStatus,
} from '../../core/orders/orders.models';
import { OrdersService } from '../../core/orders/orders.service';
import { OrderEditor, OrderEditorForm, OrderItemEditorForm } from './order-editor/order-editor';

const EMPTY_PAGINATION: OrderPagination = {
  count: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
  next_page: null,
  previous_page: null,
};

type OrderTransition = 'confirm' | 'prepare' | 'deliver' | 'cancel';

interface OrderHistoryEntry {
  id: string;
  label: string;
  description: string;
  timestamp: string | null;
  tone: 'draft' | 'confirmed' | 'prepared' | 'delivered' | 'cancelled';
}

@Component({
  selector: 'app-orders',
  imports: [ReactiveFormsModule, OrderEditor],
  templateUrl: './orders.html',
  styleUrl: './orders.scss',
})
export class Orders implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly ordersService = inject(OrdersService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private workspaceSubscription: Subscription | null = null;
  private listSubscription: Subscription | null = null;
  private detailSubscription: Subscription | null = null;
  private saveSubscription: Subscription | null = null;
  private actionSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly orders = signal<Order[]>([]);
  readonly options = signal<OrderOptionsResponse | null>(null);
  readonly pagination = signal<OrderPagination>({ ...EMPTY_PAGINATION });
  readonly activeFilters = signal<OrderListQuery>({ ordering: '-number', page_size: 20 });

  readonly isLoading = signal(false);
  readonly isSaving = signal(false);
  readonly isDetailLoading = signal(false);
  readonly actionOrderId = signal<number | null>(null);
  readonly actionTransition = signal<OrderTransition | null>(null);
  readonly isEditorOpen = signal(false);
  readonly isDetailOpen = signal(false);
  readonly editingOrder = signal<Order | null>(null);
  readonly detailOrder = signal<Order | null>(null);

  readonly listErrorMessage = signal('');
  readonly saveErrorMessage = signal('');
  readonly detailErrorMessage = signal('');
  readonly actionErrorMessage = signal('');
  readonly successMessage = signal('');

  readonly canManageOrders = computed(() => this.options()?.permissions.manage ?? false);
  readonly draftCount = computed(
    () => this.orders().filter((order) => order.status === 'DRAFT').length,
  );
  readonly confirmedCount = computed(
    () => this.orders().filter((order) => order.status === 'CONFIRMED').length,
  );
  readonly preparedCount = computed(
    () => this.orders().filter((order) => order.status === 'PREPARED').length,
  );
  readonly deliveredCount = computed(
    () => this.orders().filter((order) => order.status === 'DELIVERED').length,
  );

  readonly filterForm = this.formBuilder.group({
    search: ['', [Validators.maxLength(150)]],
    status: this.formBuilder.control<OrderStatus | ''>(''),
    branchId: 0,
    customerId: 0,
    ordering: '-number',
  });

  readonly orderForm: OrderEditorForm = this.formBuilder.group({
    branchId: this.formBuilder.control<number | null>(null, [Validators.required]),
    warehouseId: this.formBuilder.control<number | null>(null, [Validators.required]),
    customerId: this.formBuilder.control<number | null>(null, [Validators.required]),
    notes: ['', [Validators.maxLength(2000)]],
    items: this.formBuilder.array<OrderItemEditorForm>([], [Validators.minLength(1)]),
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
      customer: value.customerId || null,
      ordering: value.ordering,
      page_size: 20,
    });
    this.loadOrders(membership.company.id, 1);
  }

  clearFilters(): void {
    const membership = this.selectedMembership();

    this.resetFilterForm();
    this.activeFilters.set({ ordering: '-number', page_size: 20 });

    if (membership) {
      this.loadOrders(membership.company.id, 1);
    }
  }

  goToPage(page: number | null): void {
    const membership = this.selectedMembership();

    if (!membership || !page || this.isLoading()) {
      return;
    }

    this.loadOrders(membership.company.id, page);
  }

  openCreateEditor(): void {
    if (!this.canManageOrders() || !this.options()) {
      return;
    }

    this.editingOrder.set(null);
    this.saveErrorMessage.set('');
    this.resetOrderForm();
    this.orderForm.controls.items.push(this.createItemForm());
    this.isEditorOpen.set(true);
  }

  openEditEditor(order: Order): void {
    if (!this.canManageOrders() || !this.options() || order.status !== 'DRAFT') {
      return;
    }

    this.resetOrderForm();
    this.orderForm.patchValue({
      branchId: order.branch,
      warehouseId: order.warehouse,
      customerId: order.customer,
      notes: order.notes,
    });

    for (const item of order.items) {
      this.orderForm.controls.items.push(this.createItemForm(item));
    }

    if (this.orderForm.controls.items.length === 0) {
      this.orderForm.controls.items.push(this.createItemForm());
    }

    this.editingOrder.set(order);
    this.saveErrorMessage.set('');
    this.isEditorOpen.set(true);
  }

  closeEditor(): void {
    if (this.isSaving()) {
      return;
    }

    this.isEditorOpen.set(false);
    this.editingOrder.set(null);
    this.saveErrorMessage.set('');
    this.resetOrderForm();
  }

  saveOrder(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canManageOrders() || this.isSaving()) {
      return;
    }

    if (this.orderForm.invalid || this.orderForm.controls.items.length === 0) {
      this.orderForm.markAllAsTouched();
      this.saveErrorMessage.set('Completa la sucursal, la bodega, el cliente y al menos un ítem.');
      return;
    }

    const value = this.orderForm.getRawValue();

    if (
      value.branchId === null ||
      value.warehouseId === null ||
      value.customerId === null ||
      value.items.some(
        (item) => item.variantId === null || item.quantity === null || item.unitPrice === null,
      )
    ) {
      this.saveErrorMessage.set('Revisa los campos obligatorios del pedido.');
      return;
    }

    const variantIds = value.items.map((item) => Number(item.variantId));

    if (new Set(variantIds).size !== variantIds.length) {
      this.saveErrorMessage.set('Una variante no puede repetirse dentro del pedido.');
      return;
    }

    const input: OrderInput = {
      branch: value.branchId,
      warehouse: value.warehouseId,
      customer: value.customerId,
      notes: value.notes.trim(),
      items: value.items.map((item) => ({
        variant: Number(item.variantId),
        quantity: Number(item.quantity),
        unit_price: Number(item.unitPrice),
      })),
    };
    const companyId = membership.company.id;
    const editingOrder = this.editingOrder();
    const request = editingOrder
      ? this.ordersService.updateOrder(companyId, editingOrder.id, input)
      : this.ordersService.createOrder(companyId, input);

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
        next: (order) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.isEditorOpen.set(false);
          this.editingOrder.set(null);
          this.successMessage.set(
            editingOrder
              ? `Pedido #${order.number} actualizado correctamente.`
              : `Pedido #${order.number} creado como borrador.`,
          );
          this.resetOrderForm();
          this.loadOrders(companyId, editingOrder ? this.pagination().page : 1);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.saveErrorMessage.set(this.messageForError(error, 'guardar el pedido'));
          }
        },
      });
  }

  openDetail(order: Order): void {
    const membership = this.selectedMembership();

    if (!membership) {
      return;
    }

    const companyId = membership.company.id;
    this.detailSubscription?.unsubscribe();
    this.detailOrder.set(order);
    this.detailErrorMessage.set('');
    this.isDetailOpen.set(true);
    this.isDetailLoading.set(true);

    this.detailSubscription = this.ordersService
      .retrieveOrder(companyId, order.id)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isDetailLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (freshOrder) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.detailOrder.set(freshOrder);
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
    if (this.actionOrderId() !== null) {
      return;
    }

    this.detailSubscription?.unsubscribe();
    this.detailSubscription = null;
    this.isDetailOpen.set(false);
    this.isDetailLoading.set(false);
    this.detailOrder.set(null);
    this.detailErrorMessage.set('');
    this.actionErrorMessage.set('');
  }

  confirmOrder(order: Order): void {
    if (order.status === 'DRAFT') {
      this.runTransition(order, 'confirm');
    }
  }

  prepareOrder(order: Order): void {
    if (order.status === 'CONFIRMED') {
      this.runTransition(order, 'prepare');
    }
  }

  deliverOrder(order: Order): void {
    if (order.status === 'PREPARED') {
      this.runTransition(order, 'deliver');
    }
  }

  cancelOrder(order: Order): void {
    if (order.status === 'DRAFT' || order.status === 'CONFIRMED' || order.status === 'PREPARED') {
      this.runTransition(order, 'cancel');
    }
  }

  canConfirm(order: Order): boolean {
    return this.canManageOrders() && order.status === 'DRAFT';
  }

  canPrepare(order: Order): boolean {
    return this.canManageOrders() && order.status === 'CONFIRMED';
  }

  canDeliver(order: Order): boolean {
    return this.canManageOrders() && order.status === 'PREPARED';
  }

  canCancel(order: Order): boolean {
    return (
      this.canManageOrders() &&
      (order.status === 'DRAFT' || order.status === 'CONFIRMED' || order.status === 'PREPARED')
    );
  }

  isTransitioning(order: Order, transition: OrderTransition): boolean {
    return this.actionOrderId() === order.id && this.actionTransition() === transition;
  }

  statusLabel(status: OrderStatus): string {
    const labels: Record<OrderStatus, string> = {
      DRAFT: 'Borrador',
      CONFIRMED: 'Confirmado',
      PREPARED: 'Preparado',
      DELIVERED: 'Entregado',
      CANCELLED: 'Anulado',
    };

    return labels[status];
  }

  branchLabel(branchId: number): string {
    const branch = this.options()?.branches.find((candidate) => candidate.id === branchId);
    return branch ? `${branch.code} · ${branch.name}` : `Sucursal ${branchId}`;
  }

  warehouseLabel(warehouseId: number): string {
    const warehouse = this.options()?.warehouses.find((candidate) => candidate.id === warehouseId);
    return warehouse ? `${warehouse.code} · ${warehouse.name}` : `Bodega ${warehouseId}`;
  }

  customerLabel(customerId: number): string {
    const customer = this.options()?.customers.find((candidate) => candidate.id === customerId);
    return customer ? `${customer.code} · ${customer.name}` : `Cliente ${customerId}`;
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

  movementLabel(kind: string): string {
    return kind === 'CONFIRMATION' ? 'Salida por confirmación' : 'Reposición por anulación';
  }

  operationalHistory(order: Order): OrderHistoryEntry[] {
    const movements = order.items.flatMap((item) => item.stock_movements);
    const confirmationAt = movements
      .filter((movement) => movement.kind === 'CONFIRMATION')
      .map((movement) => movement.created_at)
      .sort()[0];
    const cancellationAt = movements
      .filter((movement) => movement.kind === 'CANCELLATION')
      .map((movement) => movement.created_at)
      .sort()
      .at(-1);
    const history: OrderHistoryEntry[] = [
      {
        id: 'created',
        label: 'Borrador creado',
        description: 'Pedido registrado para revisión y edición.',
        timestamp: order.created_at,
        tone: 'draft',
      },
    ];

    if (
      confirmationAt ||
      order.status === 'CONFIRMED' ||
      order.status === 'PREPARED' ||
      order.status === 'DELIVERED'
    ) {
      history.push({
        id: 'confirmed',
        label: 'Pedido confirmado',
        description: 'Inventario descontado y trazabilidad registrada por ítem.',
        timestamp: confirmationAt ?? order.updated_at,
        tone: 'confirmed',
      });
    }

    if (order.status === 'PREPARED' || order.status === 'DELIVERED') {
      history.push({
        id: 'prepared',
        label: 'Pedido preparado',
        description:
          order.status === 'PREPARED'
            ? 'Preparación completada; el pedido está listo para entrega.'
            : 'Paso completado antes de la entrega; la API no conserva una hora independiente.',
        timestamp: order.status === 'PREPARED' ? order.updated_at : null,
        tone: 'prepared',
      });
    }

    if (order.status === 'DELIVERED') {
      history.push({
        id: 'delivered',
        label: 'Pedido entregado',
        description: 'Entrega final registrada; el flujo operativo quedó cerrado.',
        timestamp: order.updated_at,
        tone: 'delivered',
      });
    }

    if (order.status === 'CANCELLED') {
      history.push({
        id: 'cancelled',
        label: 'Pedido anulado',
        description: cancellationAt
          ? 'Inventario repuesto y anulación registrada.'
          : 'Borrador anulado sin movimiento de inventario.',
        timestamp: cancellationAt ?? order.updated_at,
        tone: 'cancelled',
      });
    }

    return history;
  }

  private loadWorkspace(companyId: number): void {
    this.workspaceSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.listErrorMessage.set('');

    this.workspaceSubscription = forkJoin({
      options: this.ordersService.getOptions(companyId),
      list: this.ordersService.listOrders(companyId, {
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
          this.orders.set(list.orders);
          this.pagination.set(list.pagination);

          if (!options.permissions.manage) {
            this.listErrorMessage.set(
              'No tienes permiso para administrar pedidos en las sucursales de esta empresa.',
            );
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.orders.set([]);
            this.options.set(null);
            this.pagination.set({ ...EMPTY_PAGINATION });
            this.listErrorMessage.set(this.messageForError(error, 'cargar los pedidos'));
          }
        },
      });
  }

  private loadOrders(companyId: number, page: number): void {
    this.listSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.listErrorMessage.set('');
    this.actionErrorMessage.set('');

    this.listSubscription = this.ordersService
      .listOrders(companyId, {
        ...this.activeFilters(),
        page,
      })
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
            this.orders.set(response.orders);
            this.pagination.set(response.pagination);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.orders.set([]);
            this.pagination.set({ ...EMPTY_PAGINATION, page });
            this.listErrorMessage.set(this.messageForError(error, 'cargar los pedidos'));
          }
        },
      });
  }

  private runTransition(order: Order, transition: OrderTransition): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canManageOrders() || this.actionOrderId() !== null) {
      return;
    }

    const companyId = membership.company.id;
    let request: Observable<Order>;

    switch (transition) {
      case 'confirm':
        request = this.ordersService.confirmOrder(companyId, order.id);
        break;
      case 'prepare':
        request = this.ordersService.prepareOrder(companyId, order.id);
        break;
      case 'deliver':
        request = this.ordersService.deliverOrder(companyId, order.id);
        break;
      case 'cancel':
        request = this.ordersService.cancelOrder(companyId, order.id);
        break;
    }

    this.actionSubscription?.unsubscribe();
    this.actionOrderId.set(order.id);
    this.actionTransition.set(transition);
    this.actionErrorMessage.set('');
    this.successMessage.set('');

    this.actionSubscription = request
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.actionOrderId.set(null);
            this.actionTransition.set(null);
          }
        }),
      )
      .subscribe({
        next: (updatedOrder) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.detailOrder.set(
            this.detailOrder()?.id === updatedOrder.id ? updatedOrder : this.detailOrder(),
          );
          const successMessages: Record<OrderTransition, string> = {
            confirm: `Pedido #${updatedOrder.number} confirmado y descontado de inventario.`,
            prepare: `Pedido #${updatedOrder.number} preparado y listo para entrega.`,
            deliver: `Pedido #${updatedOrder.number} entregado correctamente.`,
            cancel:
              order.status === 'DRAFT'
                ? `Pedido #${updatedOrder.number} anulado correctamente.`
                : `Pedido #${updatedOrder.number} anulado y con inventario repuesto.`,
          };
          this.successMessage.set(successMessages[transition]);
          this.loadOrders(companyId, this.pagination().page);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id === companyId) {
            const actionLabels: Record<OrderTransition, string> = {
              confirm: 'confirmar el pedido',
              prepare: 'preparar el pedido',
              deliver: 'entregar el pedido',
              cancel: 'anular el pedido',
            };
            this.actionErrorMessage.set(this.messageForError(error, actionLabels[transition]));
          }
        },
      });
  }

  private createItemForm(item?: OrderItem): OrderItemEditorForm {
    return this.formBuilder.group({
      variantId: this.formBuilder.control<number | null>(item?.variant ?? null, [
        Validators.required,
      ]),
      quantity: this.formBuilder.control<number | null>(item ? Number(item.quantity) : 1, [
        Validators.required,
        Validators.min(0.001),
      ]),
      unitPrice: this.formBuilder.control<number | null>(item ? Number(item.unit_price) : null, [
        Validators.required,
        Validators.min(0),
      ]),
    });
  }

  private resetWorkspace(): void {
    this.orders.set([]);
    this.options.set(null);
    this.pagination.set({ ...EMPTY_PAGINATION });
    this.activeFilters.set({ ordering: '-number', page_size: 20 });
    this.isLoading.set(false);
    this.isSaving.set(false);
    this.isDetailLoading.set(false);
    this.actionOrderId.set(null);
    this.actionTransition.set(null);
    this.isEditorOpen.set(false);
    this.isDetailOpen.set(false);
    this.editingOrder.set(null);
    this.detailOrder.set(null);
    this.listErrorMessage.set('');
    this.saveErrorMessage.set('');
    this.detailErrorMessage.set('');
    this.actionErrorMessage.set('');
    this.successMessage.set('');
    this.resetFilterForm();
    this.resetOrderForm();
  }

  private resetFilterForm(): void {
    this.filterForm.reset({
      search: '',
      status: '',
      branchId: 0,
      customerId: 0,
      ordering: '-number',
    });
  }

  private resetOrderForm(): void {
    this.orderForm.reset({
      branchId: null,
      warehouseId: null,
      customerId: null,
      notes: '',
    });
    this.orderForm.controls.items.clear();
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
      return 'El pedido no existe o quedó fuera de tu alcance autorizado.';
    }

    if (error.status === 409) {
      return 'El estado actual del pedido no permite realizar esta acción.';
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
    this.saveSubscription?.unsubscribe();
    this.actionSubscription?.unsubscribe();
    this.workspaceSubscription = null;
    this.listSubscription = null;
    this.detailSubscription = null;
    this.saveSubscription = null;
    this.actionSubscription = null;
  }
}
