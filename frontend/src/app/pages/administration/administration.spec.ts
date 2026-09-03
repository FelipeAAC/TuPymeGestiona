import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { AdministrationService } from '../../core/administration/administration.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { Administration } from './administration';


describe('Administration', () => {
  let fixture: ComponentFixture<Administration>;
  let component: Administration;
  const membership = signal<OrganizationMembership | null>({
    id: 1,
    status: 'ACTIVE',
    company: { id: 10, name: 'Comercial Andina' },
    branches: [{ id: 5, code: 'CASA', name: 'Casa Matriz' }],
    permissions: ['administration.manage'],
  });

  const overview = {
    company: {
      id: 10,
      name: 'Comercial Andina',
      rut: '12345678-5',
      legal_name: 'Comercial Andina SpA',
      business_activity: 'Comercio',
      contact_email: 'contacto@example.com',
      phone: '',
      address: '',
      commune: '',
      city: 'Santiago',
      is_active: true,
    },
    branches: [{ id: 5, company: 10, code: 'CASA', name: 'Casa Matriz', address: '', commune: '', city: '', phone: '', is_active: true }],
    users: [{ id: 2, user_id: 4, username: 'ana', email: 'ana@example.com', first_name: 'Ana', last_name: 'Torres', status: 'ACTIVE', branch_ids: [5], role_ids: [3], role_names: ['Administrador'] }],
    roles: [{ id: 3, name: 'Administrador', status: 'ACTIVE', permission_codes: ['administration.manage'] }],
    permissions: [{ id: 8, code: 'administration.manage', scope_behavior: 'COMPANY_ONLY' }],
    payment_methods: [{ id: 6, code: 'CASH', name: 'Efectivo', kind: 'CASH', is_active: true, sort_order: 10 }],
    order_statuses: [{ id: 7, code: 'DRAFT', display_name: 'Borrador', sort_order: 10, is_active: true, is_system: true }],
    settings: { vat_rate: '19.00', currency: 'CLP', timezone: 'America/Santiago', payment_provider: 'MERCADO_PAGO', payment_sandbox_enabled: true, notification_sender_email: '', updated_at: '' },
    events: [],
  } as const;

  const administrationService = {
    loadOverview: vi.fn(() => of(overview)),
    updateCompany: vi.fn(() => of(overview.company)),
    createBranch: vi.fn(),
    updateBranch: vi.fn(),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    createRole: vi.fn(),
    updateRole: vi.fn(),
    createPaymentMethod: vi.fn(),
    updatePaymentMethod: vi.fn(),
    updateOrderStatus: vi.fn(),
    updateSettings: vi.fn(() => of(overview.settings)),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Administration],
      providers: [
        { provide: AdministrationService, useValue: administrationService },
        { provide: OrganizationContextService, useValue: { selectedMembership: membership.asReadonly() } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Administration);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads administration for the active company', () => {
    expect(administrationService.loadOverview).toHaveBeenCalledWith(10);
    expect(fixture.nativeElement.textContent).toContain('Administración');
    expect(fixture.nativeElement.textContent).toContain('Ana Torres');
  });

  it('shows the main administrative tabs', () => {
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Roles y permisos');
    expect(text).toContain('Sucursales');
    expect(text).toContain('Métodos de pago');
    expect(text).toContain('Parámetros');
  });

  it('does not load data when the membership lacks administration permission', () => {
    membership.set({ ...membership()!, permissions: [] });
    fixture.detectChanges();
    expect(component.canAdminister()).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('no tiene el permiso');
    membership.set({ ...membership()!, permissions: ['administration.manage'] });
  });
});
