import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Order, OrderInput, OrderListResponse, OrderOptionsResponse } from './orders.models';
import { OrdersService } from './orders.service';

describe('OrdersService', () => {
  let service: OrdersService;
  let httpTesting: HttpTestingController;

  const order: Order = {
    id: 15,
    company: 7,
    branch: 3,
    warehouse: 12,
    customer: 21,
    number: 104,
    status: 'DRAFT',
    notes: 'Entrega en horario de oficina',
    created_by: 5,
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-01T10:00:00Z',
    items: [],
    total: '0.00',
  };

  const input: OrderInput = {
    branch: 3,
    warehouse: 12,
    customer: 21,
    notes: 'Entrega en horario de oficina',
    items: [{ variant: 30, quantity: 2, unit_price: 4500 }],
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(OrdersService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('loads the branch-scoped options for the selected company', () => {
    const response: OrderOptionsResponse = {
      permissions: { manage: true },
      branches: [],
      warehouses: [],
      customers: [],
      variants: [],
    };

    service.getOptions(7).subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/orders/options/' && candidate.params.get('company') === '7',
    );

    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('lists orders with filters and stable pagination parameters', () => {
    const response: OrderListResponse = {
      orders: [order],
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
      .listOrders(7, {
        status: 'DRAFT',
        branch: 3,
        customer: 21,
        search: '  Andina  ',
        ordering: 'number',
        page: 2,
        page_size: 10,
      })
      .subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne((candidate) => candidate.url === '/api/orders/');

    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('company')).toBe('7');
    expect(request.request.params.get('status')).toBe('DRAFT');
    expect(request.request.params.get('branch')).toBe('3');
    expect(request.request.params.get('customer')).toBe('21');
    expect(request.request.params.get('search')).toBe('Andina');
    expect(request.request.params.get('ordering')).toBe('number');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('10');
    request.flush(response);
  });

  it('retrieves an order inside the selected company', () => {
    service.retrieveOrder(7, 15).subscribe((result) => expect(result).toEqual(order));

    const request = httpTesting.expectOne(
      (candidate) => candidate.url === '/api/orders/15/' && candidate.params.get('company') === '7',
    );

    expect(request.request.method).toBe('GET');
    request.flush({ order });
  });

  it('creates and updates a draft with the selected company bound in the body', () => {
    service.createOrder(7, input).subscribe((result) => expect(result).toEqual(order));

    const createRequest = httpTesting.expectOne('/api/orders/');
    expect(createRequest.request.method).toBe('POST');
    expect(createRequest.request.body).toEqual({ company: 7, ...input });
    createRequest.flush({ order });

    service.updateOrder(7, 15, input).subscribe((result) => expect(result).toEqual(order));

    const updateRequest = httpTesting.expectOne('/api/orders/15/');
    expect(updateRequest.request.method).toBe('PATCH');
    expect(updateRequest.request.body).toEqual({ company: 7, ...input });
    updateRequest.flush({ order });
  });

  it('runs every order state change through its explicit transition endpoint', () => {
    service.confirmOrder(7, 15).subscribe((result) => expect(result).toEqual(order));

    const confirmRequest = httpTesting.expectOne('/api/orders/15/confirm/');
    expect(confirmRequest.request.method).toBe('POST');
    expect(confirmRequest.request.body).toEqual({ company: 7 });
    confirmRequest.flush({ order });

    service.prepareOrder(7, 15).subscribe((result) => expect(result).toEqual(order));

    const prepareRequest = httpTesting.expectOne('/api/orders/15/prepare/');
    expect(prepareRequest.request.method).toBe('POST');
    expect(prepareRequest.request.body).toEqual({ company: 7 });
    prepareRequest.flush({ order });

    service.deliverOrder(7, 15).subscribe((result) => expect(result).toEqual(order));

    const deliverRequest = httpTesting.expectOne('/api/orders/15/deliver/');
    expect(deliverRequest.request.method).toBe('POST');
    expect(deliverRequest.request.body).toEqual({ company: 7 });
    deliverRequest.flush({ order });

    service.cancelOrder(7, 15).subscribe((result) => expect(result).toEqual(order));

    const cancelRequest = httpTesting.expectOne('/api/orders/15/cancel/');
    expect(cancelRequest.request.method).toBe('POST');
    expect(cancelRequest.request.body).toEqual({ company: 7 });
    cancelRequest.flush({ order });
  });
});
