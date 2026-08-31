import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Warehouse, WarehouseInput, WarehouseListResponse } from './warehouses.models';
import { WarehousesService } from './warehouses.service';

describe('WarehousesService', () => {
  let service: WarehousesService;
  let httpTesting: HttpTestingController;

  const warehouse: Warehouse = {
    id: 12,
    company: 7,
    branch: 3,
    code: 'BOD-CENTRAL',
    name: 'Bodega Central',
  };

  const input: WarehouseInput = {
    branch: 3,
    code: 'BOD-CENTRAL',
    name: 'Bodega Central',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(WarehousesService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('lists warehouses inside the selected company', () => {
    const response: WarehouseListResponse = { warehouses: [warehouse] };

    service.listWarehouses(7).subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/organizations/warehouses/' &&
        candidate.params.get('company') === '7',
    );

    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('retrieves a warehouse inside the selected company', () => {
    service.retrieveWarehouse(7, 12).subscribe((result) => expect(result).toEqual(warehouse));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/organizations/warehouses/12/' &&
        candidate.params.get('company') === '7',
    );

    expect(request.request.method).toBe('GET');
    request.flush({ warehouse });
  });

  it('creates a warehouse inside the selected company', () => {
    service.createWarehouse(7, input).subscribe((result) => expect(result).toEqual(warehouse));

    const request = httpTesting.expectOne('/api/organizations/warehouses/');

    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ company: 7, ...input });
    request.flush({ warehouse });
  });

  it('updates a warehouse inside the selected company', () => {
    const updatedWarehouse: Warehouse = {
      ...warehouse,
      branch: null,
      name: 'Bodega General',
    };
    const updatedInput: WarehouseInput = {
      ...input,
      branch: null,
      name: 'Bodega General',
    };

    service
      .updateWarehouse(7, 12, updatedInput)
      .subscribe((result) => expect(result).toEqual(updatedWarehouse));

    const request = httpTesting.expectOne('/api/organizations/warehouses/12/');

    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ company: 7, ...updatedInput });
    request.flush({ warehouse: updatedWarehouse });
  });
});
