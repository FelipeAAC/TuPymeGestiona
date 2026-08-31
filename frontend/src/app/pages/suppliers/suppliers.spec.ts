import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { Supplier, SupplierListResponse } from '../../core/suppliers/suppliers.models';
import { SuppliersService } from '../../core/suppliers/suppliers.service';
import { Suppliers } from './suppliers';

describe('Suppliers', () => {
  let component: Suppliers;
  let fixture: ComponentFixture<Suppliers>;

  const membership: OrganizationMembership = {
    id: 2,
    status: 'ACTIVE',
    company: {
      id: 7,
      name: 'Comercial Andina SpA',
    },
    branches: [],
  };

  const supplier: Supplier = {
    id: 10,
    name: 'Distribuidora Andina',
    contact_name: 'Camila Rojas',
    email: 'camila@andina.cl',
    phone: '+56 9 1234 5678',
    status: 'ACTIVE',
  };

  const inactiveSupplier: Supplier = {
    id: 11,
    name: 'Insumos del Sur',
    contact_name: 'Diego Soto',
    email: 'diego@insumos.cl',
    phone: '+56 9 8765 4321',
    status: 'INACTIVE',
  };

  const listResponse: SupplierListResponse = {
    suppliers: [supplier, inactiveSupplier],
  };

  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const suppliersService = {
    listSuppliers: vi.fn(() => of(listResponse)),
    createSupplier: vi.fn(() => of(supplier)),
    updateSupplier: vi.fn(() => of(inactiveSupplier)),
  };
  const organizationContextService = {
    selectedMembership: selectedMembership.asReadonly(),
  };

  beforeEach(async () => {
    suppliersService.listSuppliers.mockClear();
    suppliersService.createSupplier.mockClear();
    suppliersService.updateSupplier.mockClear();
    selectedMembership.set(membership);

    await TestBed.configureTestingModule({
      imports: [Suppliers],
      providers: [
        {
          provide: SuppliersService,
          useValue: suppliersService,
        },
        {
          provide: OrganizationContextService,
          useValue: organizationContextService,
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Suppliers);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads and renders the suppliers of the selected company', () => {
    expect(suppliersService.listSuppliers).toHaveBeenCalledWith(7);
    expect(component.suppliers()).toEqual([supplier, inactiveSupplier]);
    expect(fixture.nativeElement.textContent).toContain('Distribuidora Andina');
    expect(fixture.nativeElement.textContent).toContain('Comercial Andina SpA');
  });

  it('filters suppliers locally by contact data and status', () => {
    component.filterForm.setValue({
      search: 'diego@insumos.cl',
      status: 'INACTIVE',
    });

    component.applyFilters();

    expect(component.filteredSuppliers()).toEqual([inactiveSupplier]);
    expect(suppliersService.listSuppliers).toHaveBeenCalledTimes(1);
  });

  it('creates a supplier and reloads the directory', () => {
    component.openCreateEditor();
    component.supplierForm.setValue({
      name: 'Distribuidora Andina',
      contactName: 'Camila Rojas',
      email: 'camila@andina.cl',
      phone: '+56 9 1234 5678',
      status: 'ACTIVE',
    });

    component.saveSupplier();

    expect(suppliersService.createSupplier).toHaveBeenCalledWith(7, {
      name: 'Distribuidora Andina',
      contact_name: 'Camila Rojas',
      email: 'camila@andina.cl',
      phone: '+56 9 1234 5678',
      status: 'ACTIVE',
    });
    expect(component.successMessage()).toContain('creado correctamente');
    expect(component.isEditorOpen()).toBe(false);
    expect(suppliersService.listSuppliers).toHaveBeenCalledTimes(2);
  });

  it('opens and updates an existing supplier', () => {
    component.openEditEditor(inactiveSupplier);

    expect(component.supplierForm.getRawValue()).toEqual({
      name: 'Insumos del Sur',
      contactName: 'Diego Soto',
      email: 'diego@insumos.cl',
      phone: '+56 9 8765 4321',
      status: 'INACTIVE',
    });

    component.supplierForm.patchValue({ name: 'Insumos del Sur SpA' });
    component.saveSupplier();

    expect(suppliersService.updateSupplier).toHaveBeenCalledWith(7, 11, {
      name: 'Insumos del Sur SpA',
      contact_name: 'Diego Soto',
      email: 'diego@insumos.cl',
      phone: '+56 9 8765 4321',
      status: 'INACTIVE',
    });
    expect(component.successMessage()).toContain('actualizado correctamente');
    expect(component.isEditorOpen()).toBe(false);
    expect(suppliersService.listSuppliers).toHaveBeenCalledTimes(2);
  });
});
