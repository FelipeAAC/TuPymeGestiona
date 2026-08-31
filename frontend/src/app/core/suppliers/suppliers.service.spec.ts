import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Supplier, SupplierInput, SupplierListResponse } from './suppliers.models';
import { SuppliersService } from './suppliers.service';

describe('SuppliersService', () => {
  let service: SuppliersService;
  let httpTesting: HttpTestingController;

  const supplier: Supplier = {
    id: 12,
    name: 'Distribuidora Andina',
    contact_name: 'Ana Pérez',
    email: 'ana@andina.cl',
    phone: '+56 9 1234 5678',
    status: 'ACTIVE',
  };

  const input: SupplierInput = {
    name: 'Distribuidora Andina',
    contact_name: 'Ana Pérez',
    email: 'ana@andina.cl',
    phone: '+56 9 1234 5678',
    status: 'ACTIVE',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(SuppliersService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('lists suppliers inside the selected company', () => {
    const response: SupplierListResponse = { suppliers: [supplier] };

    service.listSuppliers(7).subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/catalog/suppliers/' && candidate.params.get('company') === '7',
    );

    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('retrieves a supplier inside the selected company', () => {
    service.retrieveSupplier(7, 12).subscribe((result) => expect(result).toEqual(supplier));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/catalog/suppliers/12/' && candidate.params.get('company') === '7',
    );

    expect(request.request.method).toBe('GET');
    request.flush({ supplier });
  });

  it('creates a supplier inside the selected company', () => {
    service.createSupplier(7, input).subscribe((result) => expect(result).toEqual(supplier));

    const request = httpTesting.expectOne('/api/catalog/suppliers/');

    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ company: 7, ...input });
    request.flush({ supplier });
  });

  it('updates a supplier inside the selected company', () => {
    const updatedSupplier: Supplier = {
      ...supplier,
      status: 'INACTIVE',
    };
    const updatedInput: SupplierInput = {
      ...input,
      status: 'INACTIVE',
    };

    service
      .updateSupplier(7, 12, updatedInput)
      .subscribe((result) => expect(result).toEqual(updatedSupplier));

    const request = httpTesting.expectOne('/api/catalog/suppliers/12/');

    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ company: 7, ...updatedInput });
    request.flush({ supplier: updatedSupplier });
  });
});
