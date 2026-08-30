import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { signal } from '@angular/core';

import { Customer, CustomerListResponse } from '../../core/customers/customers.models';
import { CustomersService } from '../../core/customers/customers.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { Customers } from './customers';

describe('Customers', () => {
  let component: Customers;
  let fixture: ComponentFixture<Customers>;

  const membership: OrganizationMembership = {
    id: 2,
    status: 'ACTIVE',
    company: {
      id: 7,
      name: 'Comercial Andina SpA',
    },
    branches: [],
  };

  const customer: Customer = {
    id: 10,
    company: 7,
    code: 'CLI-001',
    name: 'Camila Rojas',
    tax_id: '18.245.771-6',
    email: 'camila@example.com',
    phone: '+56 9 1234 5678',
    status: 'ACTIVE',
    created_at: '2026-08-29T10:00:00Z',
    updated_at: '2026-08-30T10:00:00Z',
  };

  const listResponse: CustomerListResponse = {
    customers: [customer],
    pagination: {
      count: 1,
      page: 1,
      page_size: 10,
      total_pages: 1,
      next_page: null,
      previous_page: null,
    },
  };

  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const customersService = {
    listCustomers: vi.fn(() => of(listResponse)),
    createCustomer: vi.fn(() => of(customer)),
    updateCustomer: vi.fn(() => of(customer)),
  };
  const organizationContextService = {
    selectedMembership: selectedMembership.asReadonly(),
  };

  beforeEach(async () => {
    customersService.listCustomers.mockClear();
    customersService.createCustomer.mockClear();
    customersService.updateCustomer.mockClear();
    selectedMembership.set(membership);

    await TestBed.configureTestingModule({
      imports: [Customers],
      providers: [
        {
          provide: CustomersService,
          useValue: customersService,
        },
        {
          provide: OrganizationContextService,
          useValue: organizationContextService,
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Customers);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads and renders the customers of the selected company', () => {
    expect(customersService.listCustomers).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        ordering: 'name',
        page: 1,
        page_size: 10,
      }),
    );
    expect(component.customers()).toEqual([customer]);
    expect(fixture.nativeElement.textContent).toContain('Camila Rojas');
    expect(fixture.nativeElement.textContent).toContain('Comercial Andina SpA');
  });

  it('creates a customer and reloads the first page', () => {
    component.openCreateEditor();
    component.customerForm.setValue({
      code: 'CLI-001',
      name: 'Camila Rojas',
      taxId: '18.245.771-6',
      email: 'camila@example.com',
      phone: '+56 9 1234 5678',
      status: 'ACTIVE',
    });

    component.saveCustomer();

    expect(customersService.createCustomer).toHaveBeenCalledWith(7, {
      code: 'CLI-001',
      name: 'Camila Rojas',
      tax_id: '18.245.771-6',
      email: 'camila@example.com',
      phone: '+56 9 1234 5678',
      status: 'ACTIVE',
    });
    expect(component.successMessage()).toContain('creado correctamente');
    expect(component.isEditorOpen()).toBe(false);
    expect(customersService.listCustomers).toHaveBeenCalledTimes(2);
  });

  it('opens an existing customer for editing', () => {
    component.openEditEditor(customer);

    expect(component.editingCustomer()).toEqual(customer);
    expect(component.customerForm.getRawValue()).toEqual({
      code: 'CLI-001',
      name: 'Camila Rojas',
      taxId: '18.245.771-6',
      email: 'camila@example.com',
      phone: '+56 9 1234 5678',
      status: 'ACTIVE',
    });
  });

  it('updates an existing customer and reloads the current page', () => {
    component.openEditEditor(customer);
    component.customerForm.patchValue({
      name: 'Camila Rojas SpA',
      status: 'INACTIVE',
    });

    component.saveCustomer();

    expect(customersService.updateCustomer).toHaveBeenCalledWith(7, 10, {
      code: 'CLI-001',
      name: 'Camila Rojas SpA',
      tax_id: '18.245.771-6',
      email: 'camila@example.com',
      phone: '+56 9 1234 5678',
      status: 'INACTIVE',
    });
    expect(component.successMessage()).toContain('actualizado correctamente');
    expect(component.isEditorOpen()).toBe(false);
    expect(customersService.listCustomers).toHaveBeenCalledTimes(2);
  });
});
