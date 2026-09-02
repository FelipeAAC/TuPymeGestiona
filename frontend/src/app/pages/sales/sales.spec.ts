import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, Subject, throwError } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import {
  Sale,
  SaleListResponse,
  SaleOptionsResponse,
  SalePayment,
  SalePaymentResponse,
} from '../../core/sales/sales.models';
import { SalesService } from '../../core/sales/sales.service';
import { Sales } from './sales';

describe('Sales', () => {
  let component: Sales;
  let fixture: ComponentFixture<Sales>;

  const membership: OrganizationMembership = {
    id: 2,
    status: 'ACTIVE',
    company: { id: 7, name: 'Comercial Andina SpA' },
    branches: [{ id: 3, code: 'SUC-NORTE', name: 'Sucursal Norte' }],
  };

  const secondMembership: OrganizationMembership = {
    id: 4,
    status: 'ACTIVE',
    company: { id: 9, name: 'Servicios del Sur Ltda.' },
    branches: [],
  };

  const payment: SalePayment = {
    id: 44,
    amount: '3000.00',
    reference: 'TRANSFERENCIA-44',
    idempotency_key: 'payment-key',
    recorded_by: 5,
    created_at: '2026-09-02T10:30:00Z',
  };

  const pendingSale: Sale = {
    id: 31,
    company: 7,
    branch: 3,
    order: 15,
    order_number: 104,
    customer: 21,
    customer_code: 'CLI-21',
    customer_name: 'Cliente Andino',
    number: 8,
    status: 'PENDING',
    total_amount: '9000.00',
    paid_amount: '0.00',
    balance: '9000.00',
    idempotency_key: 'sale-key',
    created_by: 5,
    cancelled_by: null,
    created_at: '2026-09-02T10:00:00Z',
    updated_at: '2026-09-02T10:00:00Z',
    cancelled_at: null,
    payments: [],
    events: [
      {
        id: 70,
        event_type: 'CREATED',
        previous_status: '',
        new_status: 'PENDING',
        payment: null,
        amount: null,
        reference: '',
        performed_by: 5,
        created_at: '2026-09-02T10:00:00Z',
      },
    ],
  };

  const partialSale: Sale = {
    ...pendingSale,
    status: 'PARTIAL',
    paid_amount: '3000.00',
    balance: '6000.00',
    updated_at: '2026-09-02T10:30:00Z',
    payments: [payment],
    events: [
      ...pendingSale.events,
      {
        id: 71,
        event_type: 'PAYMENT_RECORDED',
        previous_status: 'PENDING',
        new_status: 'PARTIAL',
        payment: 44,
        amount: '3000.00',
        reference: 'TRANSFERENCIA-44',
        performed_by: 5,
        created_at: '2026-09-02T10:30:00Z',
      },
    ],
  };

  const cancelledSale: Sale = {
    ...pendingSale,
    status: 'CANCELLED',
    cancelled_by: 5,
    cancelled_at: '2026-09-02T10:45:00Z',
    updated_at: '2026-09-02T10:45:00Z',
  };

  const optionsResponse: SaleOptionsResponse = {
    permissions: { manage: true },
    branches: [{ id: 3, code: 'SUC-NORTE', name: 'Sucursal Norte' }],
    delivered_orders: [
      {
        id: 15,
        number: 104,
        branch: 3,
        customer: 21,
        customer_code: 'CLI-21',
        customer_name: 'Cliente Andino',
        total: '9000.00',
      },
    ],
  };

  const listResponse: SaleListResponse = {
    sales: [pendingSale],
    pagination: {
      count: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      next_page: null,
      previous_page: null,
    },
  };

  const emptyListResponse: SaleListResponse = {
    sales: [],
    pagination: {
      count: 0,
      page: 1,
      page_size: 20,
      total_pages: 0,
      next_page: null,
      previous_page: null,
    },
  };

  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const salesService = {
    getOptions: vi.fn((_companyId: number) => of(optionsResponse)),
    listSales: vi.fn((_companyId: number, _query: unknown) => of(listResponse)),
    retrieveSale: vi.fn((_companyId: number, _saleId: number) => of(pendingSale)),
    createSale: vi.fn((_companyId: number, _orderId: number, _key: string) =>
      of({ sale: pendingSale, idempotent_replay: false }),
    ),
    recordPayment: vi.fn(
      (_companyId: number, _saleId: number, _amount: number, _reference: string, _key: string) =>
        of({ sale: partialSale, payment, idempotent_replay: false }),
    ),
    cancelSale: vi.fn((_companyId: number, _saleId: number) =>
      of({ sale: cancelledSale, already_cancelled: false }),
    ),
  };
  const organizationContextService = {
    selectedMembership: selectedMembership.asReadonly(),
  };

  beforeEach(async () => {
    for (const mock of Object.values(salesService)) {
      mock.mockReset();
    }
    salesService.getOptions.mockReturnValue(of(optionsResponse));
    salesService.listSales.mockReturnValue(of(listResponse));
    salesService.retrieveSale.mockReturnValue(of(pendingSale));
    salesService.createSale.mockReturnValue(of({ sale: pendingSale, idempotent_replay: false }));
    salesService.recordPayment.mockReturnValue(
      of({ sale: partialSale, payment, idempotent_replay: false }),
    );
    salesService.cancelSale.mockReturnValue(of({ sale: cancelledSale, already_cancelled: false }));
    selectedMembership.set(membership);

    await TestBed.configureTestingModule({
      imports: [Sales],
      providers: [
        { provide: SalesService, useValue: salesService },
        { provide: OrganizationContextService, useValue: organizationContextService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Sales);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads and renders sales from the active company and authorized branch', () => {
    expect(salesService.getOptions).toHaveBeenCalledWith(7);
    expect(salesService.listSales).toHaveBeenCalledWith(7, {
      ordering: '-number',
      page_size: 20,
      page: 1,
    });
    expect(component.sales()).toEqual([pendingSale]);
    expect(fixture.nativeElement.textContent).toContain('Venta');
    expect(fixture.nativeElement.textContent).toContain('#8');
    expect(fixture.nativeElement.textContent).toContain('Pedido #104');
    expect(fixture.nativeElement.textContent).toContain('Cliente Andino');
  });

  it('clears the previous tenant and reloads when the company changes', async () => {
    salesService.listSales.mockImplementation((companyId) =>
      of(companyId === 7 ? listResponse : emptyListResponse),
    );

    selectedMembership.set(secondMembership);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(salesService.getOptions).toHaveBeenLastCalledWith(9);
    expect(salesService.listSales).toHaveBeenLastCalledWith(9, {
      ordering: '-number',
      page_size: 20,
      page: 1,
    });
    expect(component.sales()).toEqual([]);
  });

  it('creates a sale from an eligible delivered order with an internal idempotency key', () => {
    component.openCreate();
    component.createForm.controls.orderId.setValue(15);

    component.createSale();

    const [companyId, orderId, key] = salesService.createSale.mock.calls[0];
    expect(companyId).toBe(7);
    expect(orderId).toBe(15);
    expect(key).toMatch(/^sale-7-/);
    expect(component.successMessage()).toContain('creada desde el pedido #104');
    expect(component.isCreateOpen()).toBe(false);
    expect(salesService.getOptions).toHaveBeenCalledTimes(2);
  });

  it('keeps the same sale idempotency key when retrying a failed request', () => {
    salesService.createSale
      .mockReturnValueOnce(
        throwError(
          () =>
            new HttpErrorResponse({
              status: 0,
              error: null,
            }),
        ),
      )
      .mockReturnValueOnce(of({ sale: pendingSale, idempotent_replay: true }));
    component.openCreate();
    component.createForm.controls.orderId.setValue(15);

    component.createSale();
    component.createSale();

    expect(salesService.createSale.mock.calls[0][2]).toBe(salesService.createSale.mock.calls[1][2]);
    expect(component.successMessage()).toContain('recuperada sin duplicarla');
  });

  it('rejects a payment above the current balance before calling the API', () => {
    component.openPayment(pendingSale);
    component.paymentForm.setValue({ amount: 9000.01, reference: 'TRANSFERENCIA-45' });

    component.recordPayment();

    expect(salesService.recordPayment).not.toHaveBeenCalled();
    expect(component.paymentErrorMessage()).toContain('no puede superar el saldo');
  });

  it('records a payment with its reference and refreshes an open detail', () => {
    component.detailSale.set(pendingSale);
    component.openPayment(pendingSale);
    component.paymentForm.setValue({ amount: 3000, reference: '  TRANSFERENCIA-44  ' });

    component.recordPayment();

    const [companyId, saleId, amount, reference, key] = salesService.recordPayment.mock.calls[0];
    expect([companyId, saleId, amount, reference]).toEqual([7, 31, 3000, 'TRANSFERENCIA-44']);
    expect(key).toMatch(/^payment-7-/);
    expect(component.detailSale()).toEqual(partialSale);
    expect(component.successMessage()).toContain('registrado en la venta #8');
    expect(salesService.listSales).toHaveBeenCalledTimes(2);
  });

  it('requires explicit confirmation and only cancels an unpaid pending sale', () => {
    component.requestCancel(pendingSale);

    expect(component.cancelCandidate()).toEqual(pendingSale);
    expect(salesService.cancelSale).not.toHaveBeenCalled();

    component.confirmCancel();

    expect(salesService.cancelSale).toHaveBeenCalledWith(7, 31);
    expect(component.cancelCandidate()).toBeNull();
    expect(component.successMessage()).toContain('anulada correctamente');
    expect(component.canCancel(partialSale)).toBe(false);
  });

  it('renders payment and audit evidence in the commercial detail', () => {
    salesService.retrieveSale.mockReturnValueOnce(of(partialSale));

    component.openDetail(partialSale);
    fixture.detectChanges();

    const content = fixture.nativeElement.textContent;
    expect(content).toContain('Pagos registrados');
    expect(content).toContain('TRANSFERENCIA-44');
    expect(content).toContain('Cronología de la venta');
    expect(content).toContain('Venta creada');
    expect(content).toContain('Pago registrado');
  });

  it('shows the backend conflict detail and preserves the payment draft for retry', () => {
    salesService.recordPayment.mockReturnValueOnce(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 409,
            error: { detail: 'El pago no puede superar el saldo pendiente de la venta.' },
          }),
      ),
    );
    component.openPayment(pendingSale);
    component.paymentForm.setValue({ amount: 3000, reference: 'TRANSFERENCIA-44' });

    component.recordPayment();

    expect(component.paymentErrorMessage()).toContain('saldo pendiente');
    expect(component.isPaymentOpen()).toBe(true);
    expect(component.paymentForm.getRawValue()).toEqual({
      amount: 3000,
      reference: 'TRANSFERENCIA-44',
    });
    expect(salesService.listSales).toHaveBeenCalledTimes(1);
  });

  it('drops an in-flight payment and stale detail when the company changes', async () => {
    const request = new Subject<SalePaymentResponse>();
    salesService.recordPayment.mockReturnValueOnce(request.asObservable());
    salesService.listSales.mockImplementation((companyId) =>
      of(companyId === 7 ? listResponse : emptyListResponse),
    );
    component.detailSale.set(pendingSale);
    component.isDetailOpen.set(true);
    component.openPayment(pendingSale);
    component.paymentForm.setValue({ amount: 3000, reference: 'TRANSFERENCIA-44' });
    component.recordPayment();

    selectedMembership.set(secondMembership);
    fixture.detectChanges();
    await fixture.whenStable();
    request.next({ sale: partialSale, payment, idempotent_replay: false });
    request.complete();

    expect(salesService.getOptions).toHaveBeenLastCalledWith(9);
    expect(component.isPaymentSaving()).toBe(false);
    expect(component.isPaymentOpen()).toBe(false);
    expect(component.detailSale()).toBeNull();
    expect(component.sales()).toEqual([]);
    expect(component.successMessage()).toBe('');
  });
});
