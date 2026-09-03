import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { AppShell } from './app-shell';

describe('AppShell', () => {
  let component: AppShell;
  let fixture: ComponentFixture<AppShell>;

  const currentUser = signal(null);
  const memberships = signal<OrganizationMembership[]>([]);
  const selectedMembership = signal<OrganizationMembership | null>(null);

  beforeEach(async () => {
    memberships.set([]);
    selectedMembership.set(null);

    await TestBed.configureTestingModule({
      imports: [AppShell],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            currentUser: currentUser.asReadonly(),
            logout: vi.fn(() => of(undefined)),
          },
        },
        {
          provide: OrganizationContextService,
          useValue: {
            memberships: memberships.asReadonly(),
            selectedMembership: selectedMembership.asReadonly(),
            load: vi.fn(() => of([])),
            selectMembership: vi.fn(),
            clear: vi.fn(),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AppShell);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('shows the inventory navigation link', () => {
    const inventoryLink = fixture.nativeElement.querySelector('a[href="/app/inventory"]');

    expect(inventoryLink).toBeTruthy();
    expect(inventoryLink.textContent).toContain('Inventario');
  });

  it('shows the supplier navigation link', () => {
    const supplierLink = fixture.nativeElement.querySelector('a[href="/app/suppliers"]');

    expect(supplierLink).toBeTruthy();
    expect(supplierLink.textContent).toContain('Proveedores');
  });

  it('shows the warehouse navigation link', () => {
    const warehouseLink = fixture.nativeElement.querySelector('a[href="/app/warehouses"]');

    expect(warehouseLink).toBeTruthy();
    expect(warehouseLink.textContent).toContain('Bodegas');
  });

  it('shows the orders navigation link', () => {
    const ordersLink = fixture.nativeElement.querySelector('a[href="/app/orders"]');

    expect(ordersLink).toBeTruthy();
    expect(ordersLink.textContent).toContain('Pedidos');
  });

  it('shows the sales navigation link', () => {
    const salesLink = fixture.nativeElement.querySelector('a[href="/app/sales"]');

    expect(salesLink).toBeTruthy();
    expect(salesLink.textContent).toContain('Ventas');
  });

  it('shows the electronic tax navigation link', () => {
    const taxLink = fixture.nativeElement.querySelector('a[href="/app/electronic-tax"]');

    expect(taxLink).toBeTruthy();
    expect(taxLink.textContent).toContain('Facturación electrónica');
  });

  it('shows administration only when the selected membership has the permission', () => {
    selectedMembership.set({
      id: 1,
      status: 'ACTIVE',
      company: { id: 3, name: 'Empresa' },
      branches: [],
      permissions: ['administration.manage'],
    });
    fixture.detectChanges();

    const administrationLink = fixture.nativeElement.querySelector('a[href="/app/administration"]');
    expect(administrationLink).toBeTruthy();
    expect(administrationLink.textContent).toContain('Administración');

    selectedMembership.set(null);
  });
});
