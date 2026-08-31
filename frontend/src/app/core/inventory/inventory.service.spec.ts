import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import {
  InventoryMovementCreateResponse,
  InventoryOptionsResponse,
  InventoryTransfer,
} from './inventory.models';
import { InventoryService } from './inventory.service';

describe('InventoryService', () => {
  let service: InventoryService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(InventoryService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('loads the inventory options for the selected company', () => {
    const response: InventoryOptionsResponse = {
      permissions: {
        stocks_manage: true,
        movements_manage: true,
        transfers_manage: false,
      },
      warehouses: [],
      variants: [],
    };

    service.getOptions(7).subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne('/api/inventory/options/?company=7');

    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('lists movements using the selected filters', () => {
    service
      .listMovements(7, {
        warehouse: 3,
        variant: 9,
        movement_type: 'ENTRY',
      })
      .subscribe((movements) => expect(movements).toEqual([]));

    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/inventory/movements/' &&
        candidate.params.get('company') === '7' &&
        candidate.params.get('warehouse') === '3' &&
        candidate.params.get('variant') === '9' &&
        candidate.params.get('movement_type') === 'ENTRY',
    );

    expect(request.request.method).toBe('GET');
    request.flush({ movements: [] });
  });

  it('creates a signed inventory movement', () => {
    const response: InventoryMovementCreateResponse = {
      movement: {
        id: 11,
        warehouse: 3,
        variant: 9,
        movement_type: 'EXIT',
        quantity_delta: '-4.000',
        created_by: 2,
        created_at: '2026-08-31T12:00:00Z',
      },
      stock: {
        id: 5,
        warehouse: 3,
        variant: 9,
        quantity: '16.000',
        created_at: '2026-08-30T12:00:00Z',
        updated_at: '2026-08-31T12:00:00Z',
      },
    };

    service
      .createMovement(7, {
        warehouse: 3,
        variant: 9,
        movement_type: 'EXIT',
        quantity_delta: '-4',
      })
      .subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne('/api/inventory/movements/');

    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      company: 7,
      warehouse: 3,
      variant: 9,
      movement_type: 'EXIT',
      quantity_delta: '-4',
    });
    request.flush(response);
  });

  it('creates a transfer with its item lines', () => {
    const transfer: InventoryTransfer = {
      id: 18,
      source_warehouse: 3,
      destination_warehouse: 4,
      created_by: 2,
      status: 'COMPLETED',
      created_at: '2026-08-31T12:00:00Z',
      items: [{ variant: 9, quantity: '5.000' }],
    };

    service
      .createTransfer(7, {
        source_warehouse: 3,
        destination_warehouse: 4,
        items: [{ variant: 9, quantity: '5' }],
      })
      .subscribe((result) => expect(result).toEqual(transfer));

    const request = httpTesting.expectOne('/api/inventory/transfers/');

    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      company: 7,
      source_warehouse: 3,
      destination_warehouse: 4,
      items: [{ variant: 9, quantity: '5' }],
    });
    request.flush({ transfer });
  });
});
