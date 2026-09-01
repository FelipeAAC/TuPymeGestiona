import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { AppShell } from './app-shell';

describe('AppShell', () => {
  let component: AppShell;
  let fixture: ComponentFixture<AppShell>;

  const currentUser = signal(null);
  const memberships = signal([]);
  const selectedMembership = signal(null);

  beforeEach(async () => {
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
});
