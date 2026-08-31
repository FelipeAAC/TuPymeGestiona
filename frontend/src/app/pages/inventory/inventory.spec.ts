import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import {
  InventoryMovement,
  InventoryOptionsResponse,
  InventoryStock,
  InventoryTransfer,
} from '../../core/inventory/inventory.models';
import { InventoryService } from '../../core/inventory/inventory.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { Inventory } from './inventory';

describe('Inventory', () => {
  let component: Inventory;
  let fixture: ComponentFixture<Inventory>;

  const membership: OrganizationMembership = {
    id: 2,
    status: 'ACTIVE',
    company: {
      id: 7,
      name: 'Comercial Andina SpA',
    },
    branches: [],
  };

  const options: InventoryOptionsResponse = {
    permissions: {
      stocks_manage: true,
      movements_manage: true,
      transfers_manage: true,
    },
    warehouses: [
      {
        id: 3,
        branch: 1,
        branch_name: 'Casa matriz',
        code: 'BOD-001',
        name: 'Bodega Central',
        capabilities: {
          stocks: true,
          movements: true,
          transfers: true,
        },
      },
      {
        id: 4,
        branch: 2,
        branch_name: 'Sucursal Norte',
        code: 'BOD-002',
        name: 'Bodega Norte',
        capabilities: {
          stocks: true,
          movements: true,
          transfers: true,
        },
      },
    ],
    variants: [
      {
        id: 9,
        product: 5,
        product_name: 'Polera básica',
        sku: 'POL-NEG-M',
        gtin: '',
        status: 'ACTIVE',
      },
    ],
  };

  const stock: InventoryStock = {
    id: 5,
    warehouse: 3,
    variant: 9,
    quantity: '20.000',
    created_at: '2026-08-30T12:00:00Z',
    updated_at: '2026-08-31T12:00:00Z',
  };

  const movement: InventoryMovement = {
    id: 11,
    warehouse: 3,
    variant: 9,
    movement_type: 'ENTRY',
    quantity_delta: '20.000',
    created_by: 2,
    created_at: '2026-08-31T12:00:00Z',
  };

  const transfer: InventoryTransfer = {
    id: 18,
    source_warehouse: 3,
    destination_warehouse: 4,
    created_by: 2,
    status: 'COMPLETED',
    created_at: '2026-08-31T12:00:00Z',
    items: [{ variant: 9, quantity: '5.000' }],
  };

  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const inventoryService = {
    getOptions: vi.fn(() => of(options)),
    listStocks: vi.fn(() => of([stock])),
    listMovements: vi.fn(() => of([movement])),
    createMovement: vi.fn(() => of({ movement, stock })),
    listTransfers: vi.fn(() => of([transfer])),
    createTransfer: vi.fn(() => of(transfer)),
  };
  const organizationContextService = {
    selectedMembership: selectedMembership.asReadonly(),
  };

  beforeEach(async () => {
    Object.values(inventoryService).forEach((mock) => mock.mockClear());
    selectedMembership.set(membership);

    await TestBed.configureTestingModule({
      imports: [Inventory],
      providers: [
        {
          provide: InventoryService,
          useValue: inventoryService,
        },
        {
          provide: OrganizationContextService,
          useValue: organizationContextService,
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Inventory);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads and renders the inventory of the selected company', () => {
    expect(inventoryService.getOptions).toHaveBeenCalledWith(7);
    expect(inventoryService.listStocks).toHaveBeenCalledWith(7);
    expect(inventoryService.listMovements).toHaveBeenCalledWith(7, {});
    expect(inventoryService.listTransfers).toHaveBeenCalledWith(7);
    expect(component.stocks()).toEqual([stock]);
    expect(fixture.nativeElement.textContent).toContain('Polera básica');
    expect(fixture.nativeElement.textContent).toContain('Bodega Central');
  });

  it('registers an exit using a negative quantity delta', () => {
    component.openMovementEditor();
    component.movementForm.setValue({
      movementType: 'EXIT',
      warehouseId: 3,
      variantId: 9,
      quantity: '4',
    });

    component.saveMovement();

    expect(inventoryService.createMovement).toHaveBeenCalledWith(7, {
      warehouse: 3,
      variant: 9,
      movement_type: 'EXIT',
      quantity_delta: '-4',
    });
    expect(component.successMessage()).toContain('registrado correctamente');
    expect(component.openEditor()).toBeNull();
    expect(inventoryService.listStocks).toHaveBeenCalledTimes(2);
    expect(inventoryService.listMovements).toHaveBeenCalledTimes(2);
  });

  it('transfers an item and refreshes all inventory sections', () => {
    component.openTransferEditor();
    component.transferForm.controls.sourceWarehouseId.setValue(3);
    component.transferForm.controls.destinationWarehouseId.setValue(4);
    component.transferItems.at(0).setValue({
      variantId: 9,
      quantity: '5',
    });

    component.saveTransfer();

    expect(inventoryService.createTransfer).toHaveBeenCalledWith(7, {
      source_warehouse: 3,
      destination_warehouse: 4,
      items: [{ variant: 9, quantity: '5' }],
    });
    expect(component.successMessage()).toContain('realizada correctamente');
    expect(component.openEditor()).toBeNull();
    expect(inventoryService.listStocks).toHaveBeenCalledTimes(2);
    expect(inventoryService.listMovements).toHaveBeenCalledTimes(2);
    expect(inventoryService.listTransfers).toHaveBeenCalledTimes(2);
  });
});
