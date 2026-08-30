import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { CustomerInput, CustomerListResponse } from './customers.models';
import { CustomersService } from './customers.service';

describe('CustomersService', () => {
  let service: CustomersService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(CustomersService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('lists customers with tenant, filters and pagination', () => {
    const response: CustomerListResponse = {
      customers: [],
      pagination: {
        count: 0,
        page: 2,
        page_size: 20,
        total_pages: 0,
        next_page: null,
        previous_page: null,
      },
    };

    service
      .listCustomers(7, {
        search: 'andina',
        status: 'ACTIVE',
        ordering: '-updated_at',
        page: 2,
        page_size: 20,
      })
      .subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/customers/' &&
        candidate.params.get('company') === '7' &&
        candidate.params.get('search') === 'andina' &&
        candidate.params.get('status') === 'ACTIVE' &&
        candidate.params.get('ordering') === '-updated_at' &&
        candidate.params.get('page') === '2' &&
        candidate.params.get('page_size') === '20',
    );

    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('creates a customer inside the selected company', () => {
    const input: CustomerInput = {
      code: 'CLI-001',
      name: 'Cliente Nuevo',
      tax_id: '12.345.678-9',
      email: 'cliente@example.com',
      phone: '+56 9 1234 5678',
      status: 'ACTIVE',
    };

    service.createCustomer(4, input).subscribe((customer) => {
      expect(customer.name).toBe('Cliente Nuevo');
    });

    const request = httpTesting.expectOne('/api/customers/');

    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ company: 4, ...input });
    request.flush({
      customer: {
        id: 11,
        company: 4,
        ...input,
        created_at: '2026-08-30T10:00:00Z',
        updated_at: '2026-08-30T10:00:00Z',
      },
    });
  });

  it('updates a customer inside the selected company', () => {
    const input: CustomerInput = {
      code: 'CLI-010',
      name: 'Cliente Actualizado',
      tax_id: '',
      email: '',
      phone: '',
      status: 'INACTIVE',
    };

    service.updateCustomer(4, 10, input).subscribe((customer) => {
      expect(customer.status).toBe('INACTIVE');
    });

    const request = httpTesting.expectOne('/api/customers/10/');

    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ company: 4, ...input });
    request.flush({
      customer: {
        id: 10,
        company: 4,
        ...input,
        created_at: '2026-08-30T10:00:00Z',
        updated_at: '2026-08-30T11:00:00Z',
      },
    });
  });
});
