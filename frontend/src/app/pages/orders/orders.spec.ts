import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, Subject, throwError } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { Order, OrderListResponse, OrderOptionsResponse } from '../../core/orders/orders.models';
import { OrdersService } from '../../core/orders/orders.service';
import { Orders } from './orders';

describe('Orders', () => {
  let component: Orders;
  let fixture: ComponentFixture<Orders>;

  const membership: OrganizationMembership = {
    id: 2,
    status: 'ACTIVE',
    company: {
      id: 7,
      name: 'Comercial Andina SpA',
    },
    branches: [
      {
        id: 3,
        code: 'SUC-NORTE',
        name: 'Sucursal Norte',
      },
    ],
  };

  const secondMembership: OrganizationMembership = {
    id: 4,
    status: 'ACTIVE',
    company: {
      id: 9,
      name: 'Servicios del Sur Ltda.',
    },
    branches: [],
  };

  const draftOrder: Order = {
    id: 15,
    company: 7,
    branch: 3,
    warehouse: 12,
    customer: 21,
    number: 104,
    status: 'DRAFT',
    notes: '',
    created_by: 5,
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-01T10:00:00Z',
    items: [
      {
        id: 1,
        variant: 30,
        variant_sku: 'SKU-30',
        product_name: 'Producto de prueba',
        quantity: '2.000',
        unit_price: '4500.00',
        line_total: '9000.00',
        stock_movements: [],
      },
    ],
    total: '9000.00',
  };

  const confirmedOrder: Order = {
    ...draftOrder,
    status: 'CONFIRMED',
    updated_at: '2026-09-01T10:15:00Z',
    items: draftOrder.items.map((item) => ({
      ...item,
      stock_movements: [
        {
          id: 80,
          kind: 'CONFIRMATION',
          inventory_movement: 180,
          movement_type: 'OUT',
          quantity_delta: '-2.000',
          created_by: 5,
          created_at: '2026-09-01T10:15:00Z',
        },
      ],
    })),
  };

  const preparedOrder: Order = {
    ...confirmedOrder,
    status: 'PREPARED',
    updated_at: '2026-09-01T10:30:00Z',
  };

  const deliveredOrder: Order = {
    ...preparedOrder,
    status: 'DELIVERED',
    updated_at: '2026-09-01T11:00:00Z',
  };

  const cancelledDraftOrder: Order = {
    ...draftOrder,
    status: 'CANCELLED',
    updated_at: '2026-09-01T10:10:00Z',
  };

  const cancelledPreparedOrder: Order = {
    ...preparedOrder,
    status: 'CANCELLED',
    updated_at: '2026-09-01T10:40:00Z',
    items: preparedOrder.items.map((item) => ({
      ...item,
      stock_movements: [
        ...item.stock_movements,
        {
          id: 81,
          kind: 'CANCELLATION',
          inventory_movement: 181,
          movement_type: 'IN',
          quantity_delta: '2.000',
          created_by: 5,
          created_at: '2026-09-01T10:40:00Z',
        },
      ],
    })),
  };

  const optionsResponse: OrderOptionsResponse = {
    permissions: { manage: true },
    branches: [{ id: 3, code: 'SUC-NORTE', name: 'Sucursal Norte' }],
    warehouses: [{ id: 12, branch: 3, code: 'BOD-NORTE', name: 'Bodega Norte' }],
    customers: [{ id: 21, code: 'CLI-21', name: 'Cliente Andino' }],
    variants: [
      {
        id: 30,
        product: 40,
        product_name: 'Producto de prueba',
        sku: 'SKU-30',
        base_price: '4500.00',
      },
    ],
  };

  const listResponse: OrderListResponse = {
    orders: [draftOrder],
    pagination: {
      count: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      next_page: null,
      previous_page: null,
    },
  };

  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const ordersService = {
    getOptions: vi.fn((_companyId: number) => of(optionsResponse)),
    listOrders: vi.fn((_companyId: number, _query: unknown) => of(listResponse)),
    retrieveOrder: vi.fn((_companyId: number, _orderId: number) => of(draftOrder)),
    createOrder: vi.fn((_companyId: number, _input: unknown) => of(draftOrder)),
    updateOrder: vi.fn((_companyId: number, _orderId: number, _input: unknown) => of(draftOrder)),
    confirmOrder: vi.fn((_companyId: number, _orderId: number) => of(confirmedOrder)),
    prepareOrder: vi.fn((_companyId: number, _orderId: number) => of(preparedOrder)),
    deliverOrder: vi.fn((_companyId: number, _orderId: number) => of(deliveredOrder)),
    cancelOrder: vi.fn((_companyId: number, _orderId: number) => of(cancelledDraftOrder)),
  };
  const organizationContextService = {
    selectedMembership: selectedMembership.asReadonly(),
  };

  beforeEach(async () => {
    for (const mock of Object.values(ordersService)) {
      mock.mockReset();
    }
    ordersService.getOptions.mockReturnValue(of(optionsResponse));
    ordersService.listOrders.mockReturnValue(of(listResponse));
    ordersService.retrieveOrder.mockReturnValue(of(draftOrder));
    ordersService.createOrder.mockReturnValue(of(draftOrder));
    ordersService.updateOrder.mockReturnValue(of(draftOrder));
    ordersService.confirmOrder.mockReturnValue(of(confirmedOrder));
    ordersService.prepareOrder.mockReturnValue(of(preparedOrder));
    ordersService.deliverOrder.mockReturnValue(of(deliveredOrder));
    ordersService.cancelOrder.mockReturnValue(of(cancelledDraftOrder));
    selectedMembership.set(membership);

    await TestBed.configureTestingModule({
      imports: [Orders],
      providers: [
        {
          provide: OrdersService,
          useValue: ordersService,
        },
        {
          provide: OrganizationContextService,
          useValue: organizationContextService,
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Orders);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads and renders the authorized orders for the selected company', () => {
    expect(ordersService.getOptions).toHaveBeenCalledWith(7);
    expect(ordersService.listOrders).toHaveBeenCalledWith(7, {
      ordering: '-number',
      page_size: 20,
      page: 1,
    });
    expect(component.orders()).toEqual([draftOrder]);
    expect(fixture.nativeElement.textContent).toContain('Pedido');
    expect(fixture.nativeElement.textContent).toContain('#104');
    expect(fixture.nativeElement.textContent).toContain('Cliente Andino');
  });

  it('clears the previous tenant and reloads when the selected company changes', async () => {
    selectedMembership.set(secondMembership);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(ordersService.getOptions).toHaveBeenLastCalledWith(9);
    expect(ordersService.listOrders).toHaveBeenLastCalledWith(9, {
      ordering: '-number',
      page_size: 20,
      page: 1,
    });
  });

  it('creates a draft with items and reloads the first page', () => {
    component.openCreateEditor();
    component.orderForm.patchValue({
      branchId: 3,
      warehouseId: 12,
      customerId: 21,
      notes: 'Entrega prioritaria',
    });
    component.orderForm.controls.items.at(0).setValue({
      variantId: 30,
      quantity: 2,
      unitPrice: 4500,
    });

    component.saveOrder();

    expect(ordersService.createOrder).toHaveBeenCalledWith(7, {
      branch: 3,
      warehouse: 12,
      customer: 21,
      notes: 'Entrega prioritaria',
      items: [{ variant: 30, quantity: 2, unit_price: 4500 }],
    });
    expect(component.successMessage()).toContain('creado como borrador');
    expect(component.isEditorOpen()).toBe(false);
    expect(ordersService.listOrders).toHaveBeenCalledTimes(2);
  });

  it('confirms a draft and refreshes the current page', () => {
    component.confirmOrder(draftOrder);

    expect(ordersService.confirmOrder).toHaveBeenCalledWith(7, 15);
    expect(component.successMessage()).toContain('confirmado');
    expect(ordersService.listOrders).toHaveBeenCalledTimes(2);
  });

  it('prepares a confirmed order and exposes its loading state until completion', () => {
    const transition = new Subject<Order>();
    ordersService.prepareOrder.mockReturnValueOnce(transition.asObservable());
    component.orders.set([confirmedOrder]);
    fixture.detectChanges();

    component.prepareOrder(confirmedOrder);
    fixture.detectChanges();

    expect(ordersService.prepareOrder).toHaveBeenCalledWith(7, 15);
    expect(component.actionOrderId()).toBe(15);
    expect(component.actionTransition()).toBe('prepare');
    expect(fixture.nativeElement.textContent).toContain('Preparando...');

    transition.next(preparedOrder);
    transition.complete();
    fixture.detectChanges();

    expect(component.successMessage()).toContain('preparado y listo para entrega');
    expect(component.actionOrderId()).toBeNull();
    expect(component.actionTransition()).toBeNull();
    expect(ordersService.listOrders).toHaveBeenCalledTimes(2);
  });

  it('delivers a prepared order and refreshes an open detail with the returned state', () => {
    component.detailOrder.set(preparedOrder);

    component.deliverOrder(preparedOrder);

    expect(ordersService.deliverOrder).toHaveBeenCalledWith(7, 15);
    expect(component.detailOrder()).toEqual(deliveredOrder);
    expect(component.successMessage()).toContain('entregado correctamente');
    expect(ordersService.listOrders).toHaveBeenCalledTimes(2);
  });

  it('allows cancelling a prepared order and reports the inventory restoration', () => {
    ordersService.cancelOrder.mockReturnValueOnce(of(cancelledPreparedOrder));

    component.cancelOrder(preparedOrder);

    expect(component.canCancel(preparedOrder)).toBe(true);
    expect(ordersService.cancelOrder).toHaveBeenCalledWith(7, 15);
    expect(component.successMessage()).toContain('inventario repuesto');
  });

  it('does not call transition endpoints from an invalid local state', () => {
    component.confirmOrder(confirmedOrder);
    component.prepareOrder(draftOrder);
    component.deliverOrder(confirmedOrder);
    component.cancelOrder(deliveredOrder);

    expect(ordersService.confirmOrder).not.toHaveBeenCalled();
    expect(ordersService.prepareOrder).not.toHaveBeenCalled();
    expect(ordersService.deliverOrder).not.toHaveBeenCalled();
    expect(ordersService.cancelOrder).not.toHaveBeenCalled();
  });

  it('shows the API conflict detail without refreshing the list', () => {
    ordersService.deliverOrder.mockReturnValueOnce(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 409,
            error: { detail: 'El pedido cambió de estado. Actualiza la lista.' },
          }),
      ),
    );

    component.deliverOrder(preparedOrder);

    expect(component.actionErrorMessage()).toBe('El pedido cambió de estado. Actualiza la lista.');
    expect(component.actionOrderId()).toBeNull();
    expect(ordersService.listOrders).toHaveBeenCalledTimes(1);
  });

  it('builds an honest operational history without inventing the preparation time', () => {
    const deliveredHistory = component.operationalHistory(deliveredOrder);
    const cancelledHistory = component.operationalHistory(cancelledPreparedOrder);

    expect(deliveredHistory.map((entry) => entry.label)).toEqual([
      'Borrador creado',
      'Pedido confirmado',
      'Pedido preparado',
      'Pedido entregado',
    ]);
    expect(deliveredHistory.find((entry) => entry.id === 'confirmed')?.timestamp).toBe(
      '2026-09-01T10:15:00Z',
    );
    expect(deliveredHistory.find((entry) => entry.id === 'prepared')?.timestamp).toBeNull();
    expect(cancelledHistory.at(-1)).toMatchObject({
      id: 'cancelled',
      timestamp: '2026-09-01T10:40:00Z',
    });
  });

  it('drops an in-flight action and old detail when the selected company changes', async () => {
    const transition = new Subject<Order>();
    const emptyListResponse: OrderListResponse = {
      orders: [],
      pagination: {
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        next_page: null,
        previous_page: null,
      },
    };
    ordersService.deliverOrder.mockReturnValueOnce(transition.asObservable());
    ordersService.listOrders.mockImplementation((companyId) =>
      of(companyId === 7 ? listResponse : emptyListResponse),
    );
    component.detailOrder.set(preparedOrder);
    component.isDetailOpen.set(true);
    component.deliverOrder(preparedOrder);

    selectedMembership.set(secondMembership);
    fixture.detectChanges();
    await fixture.whenStable();
    transition.next(deliveredOrder);
    transition.complete();

    expect(ordersService.getOptions).toHaveBeenLastCalledWith(9);
    expect(component.actionOrderId()).toBeNull();
    expect(component.detailOrder()).toBeNull();
    expect(component.isDetailOpen()).toBe(false);
    expect(component.orders()).toEqual([]);
    expect(component.successMessage()).toBe('');
  });
});
