import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Sale, SaleListResponse, SaleOptionsResponse, SalePayment } from './sales.models';
import { SalesService } from './sales.service';

describe('SalesService', () => {
  let service: SalesService;
  let httpTesting: HttpTestingController;

  const sale: Sale = {
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
    events: [],
  };

  const payment: SalePayment = {
    id: 44,
    amount: '3000.00',
    reference: 'TRANSFERENCIA-44',
    idempotency_key: 'payment-key',
    recorded_by: 5,
    created_at: '2026-09-02T10:30:00Z',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(SalesService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('loads only sale options authorized for the selected company', () => {
    const response: SaleOptionsResponse = {
      permissions: { manage: true },
      branches: [{ id: 3, code: 'SUC-NORTE', name: 'Sucursal Norte' }],
      delivered_orders: [],
    };

    service.getOptions(7).subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/sales/options/' && candidate.params.get('company') === '7',
    );
    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('lists sales with trimmed filters and stable pagination', () => {
    const response: SaleListResponse = {
      sales: [sale],
      pagination: {
        count: 1,
        page: 2,
        page_size: 10,
        total_pages: 2,
        next_page: null,
        previous_page: 1,
      },
    };

    service
      .listSales(7, {
        status: 'PARTIAL',
        branch: 3,
        customer: 21,
        search: '  transferencia  ',
        ordering: 'number',
        page: 2,
        page_size: 10,
      })
      .subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne((candidate) => candidate.url === '/api/sales/');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('company')).toBe('7');
    expect(request.request.params.get('status')).toBe('PARTIAL');
    expect(request.request.params.get('branch')).toBe('3');
    expect(request.request.params.get('customer')).toBe('21');
    expect(request.request.params.get('search')).toBe('transferencia');
    expect(request.request.params.get('ordering')).toBe('number');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('10');
    request.flush(response);
  });

  it('retrieves a sale in the selected company scope', () => {
    service.retrieveSale(7, 31).subscribe((result) => expect(result).toEqual(sale));

    const request = httpTesting.expectOne(
      (candidate) => candidate.url === '/api/sales/31/' && candidate.params.get('company') === '7',
    );
    expect(request.request.method).toBe('GET');
    request.flush({ sale });
  });

  it('creates a sale with its generated idempotency key', () => {
    service.createSale(7, 15, 'sale-key').subscribe((result) => {
      expect(result.sale).toEqual(sale);
      expect(result.idempotent_replay).toBe(false);
    });

    const request = httpTesting.expectOne('/api/sales/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      company: 7,
      order: 15,
      idempotency_key: 'sale-key',
    });
    request.flush({ sale, idempotent_replay: false });
  });

  it('records an idempotent payment and cancels through explicit action endpoints', () => {
    service.recordPayment(7, 31, 3000, 'TRANSFERENCIA-44', 'payment-key').subscribe((result) => {
      expect(result.payment).toEqual(payment);
    });

    const paymentRequest = httpTesting.expectOne('/api/sales/31/payments/');
    expect(paymentRequest.request.method).toBe('POST');
    expect(paymentRequest.request.body).toEqual({
      company: 7,
      amount: 3000,
      reference: 'TRANSFERENCIA-44',
      idempotency_key: 'payment-key',
    });
    paymentRequest.flush({ sale, payment, idempotent_replay: false });

    service.cancelSale(7, 31).subscribe((result) => expect(result.sale).toEqual(sale));

    const cancelRequest = httpTesting.expectOne('/api/sales/31/cancel/');
    expect(cancelRequest.request.method).toBe('POST');
    expect(cancelRequest.request.body).toEqual({ company: 7 });
    cancelRequest.flush({ sale, already_cancelled: false });
  });
});
