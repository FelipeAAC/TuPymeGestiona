import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { Warehouse, WarehouseListResponse } from '../../core/warehouses/warehouses.models';
import { WarehousesService } from '../../core/warehouses/warehouses.service';
import { Warehouses } from './warehouses';

describe('Warehouses', () => {
  let component: Warehouses;
  let fixture: ComponentFixture<Warehouses>;

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
      {
        id: 4,
        code: 'SUC-SUR',
        name: 'Sucursal Sur',
      },
    ],
  };

  const warehouse: Warehouse = {
    id: 10,
    company: 7,
    branch: 3,
    code: 'BOD-NORTE',
    name: 'Bodega Norte',
  };

  const generalWarehouse: Warehouse = {
    id: 11,
    company: 7,
    branch: null,
    code: 'BOD-GENERAL',
    name: 'Bodega General',
  };

  const updatedWarehouse: Warehouse = {
    ...generalWarehouse,
    branch: 4,
    name: 'Bodega Sur Actualizada',
  };

  const listResponse: WarehouseListResponse = {
    warehouses: [warehouse, generalWarehouse],
  };

  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const warehousesService = {
    listWarehouses: vi.fn(() => of(listResponse)),
    createWarehouse: vi.fn(() => of(warehouse)),
    updateWarehouse: vi.fn(() => of(updatedWarehouse)),
  };
  const organizationContextService = {
    selectedMembership: selectedMembership.asReadonly(),
  };

  beforeEach(async () => {
    warehousesService.listWarehouses.mockClear();
    warehousesService.createWarehouse.mockClear();
    warehousesService.updateWarehouse.mockClear();
    selectedMembership.set(membership);

    await TestBed.configureTestingModule({
      imports: [Warehouses],
      providers: [
        {
          provide: WarehousesService,
          useValue: warehousesService,
        },
        {
          provide: OrganizationContextService,
          useValue: organizationContextService,
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Warehouses);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads and renders the warehouses of the selected company', () => {
    expect(warehousesService.listWarehouses).toHaveBeenCalledWith(7);
    expect(component.warehouses()).toEqual([warehouse, generalWarehouse]);
    expect(fixture.nativeElement.textContent).toContain('Bodega Norte');
    expect(fixture.nativeElement.textContent).toContain('Sucursal Norte');
    expect(fixture.nativeElement.textContent).toContain('Comercial Andina SpA');
  });

  it('filters warehouses locally by branch data and branch selection', () => {
    component.filterForm.setValue({
      search: 'suc-norte',
      branchId: 3,
    });

    component.applyFilters();

    expect(component.filteredWarehouses()).toEqual([warehouse]);
    expect(warehousesService.listWarehouses).toHaveBeenCalledTimes(1);
  });

  it('creates a warehouse and reloads the directory', () => {
    component.openCreateEditor();
    component.warehouseForm.setValue({
      code: 'BOD-NORTE',
      name: 'Bodega Norte',
      branchId: 3,
    });

    component.saveWarehouse();

    expect(warehousesService.createWarehouse).toHaveBeenCalledWith(7, {
      branch: 3,
      code: 'BOD-NORTE',
      name: 'Bodega Norte',
    });
    expect(component.successMessage()).toContain('creada correctamente');
    expect(component.isEditorOpen()).toBe(false);
    expect(warehousesService.listWarehouses).toHaveBeenCalledTimes(2);
  });

  it('opens and updates an existing warehouse', () => {
    component.openEditEditor(generalWarehouse);

    expect(component.warehouseForm.getRawValue()).toEqual({
      code: 'BOD-GENERAL',
      name: 'Bodega General',
      branchId: null,
    });

    component.warehouseForm.patchValue({
      name: 'Bodega Sur Actualizada',
      branchId: 4,
    });
    component.saveWarehouse();

    expect(warehousesService.updateWarehouse).toHaveBeenCalledWith(7, 11, {
      branch: 4,
      code: 'BOD-GENERAL',
      name: 'Bodega Sur Actualizada',
    });
    expect(component.successMessage()).toContain('actualizada correctamente');
    expect(component.isEditorOpen()).toBe(false);
    expect(warehousesService.listWarehouses).toHaveBeenCalledTimes(2);
  });
});
