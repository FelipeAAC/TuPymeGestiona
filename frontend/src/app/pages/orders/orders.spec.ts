import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

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
    getOptions: vi.fn(() => of(optionsResponse)),
    listOrders: vi.fn(() => of(listResponse)),
    retrieveOrder: vi.fn(() => of(draftOrder)),
    createOrder: vi.fn(() => of(draftOrder)),
    updateOrder: vi.fn(() => of(draftOrder)),
    confirmOrder: vi.fn(() => of(confirmedOrder)),
    cancelOrder: vi.fn(() => of({ ...draftOrder, status: 'CANCELLED' as const })),
  };
  const organizationContextService = {
    selectedMembership: selectedMembership.asReadonly(),
  };

  beforeEach(async () => {
    for (const mock of Object.values(ordersService)) {
      mock.mockClear();
    }
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
});
