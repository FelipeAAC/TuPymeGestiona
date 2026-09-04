import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { DashboardService } from '../../core/dashboard/dashboard.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { Dashboard } from './dashboard';

describe('Dashboard', () => {
  let fixture: ComponentFixture<Dashboard>;
  const membership = signal<OrganizationMembership | null>({
    id: 1,
    status: 'ACTIVE',
    company: { id: 3, name: 'Empresa Dashboard' },
    branches: [],
    permissions: ['administration.manage'],
  });
  const getOverview = vi.fn(() =>
    of({
      company: { id: 3, name: 'Empresa Dashboard' },
      generated_at: '2026-09-04T00:00:00-04:00',
      permissions: {
        sales: true,
        orders: true,
        inventory: true,
        customers: true,
        reports: true,
        administration: true,
      },
      metrics: {
        sales_today_amount: '1000.00',
        sales_today_count: 1,
        pending_orders: 2,
        low_stock: 1,
        critical_stock: 1,
        out_of_stock: 0,
        active_customers: 4,
      },
      alerts: [
        {
          code: 'inventory-critical',
          severity: 'warning' as const,
          title: 'Stock crítico',
          detail: '1 existencia requiere reposición.',
          count: 1,
          route: '/app/inventory',
        },
      ],
      activity: [
        {
          kind: 'sale' as const,
          title: 'Venta creada',
          detail: 'Venta #1 · Casa Matriz',
          occurred_at: '2026-09-04T00:00:00-04:00',
          route: '/app/sales',
        },
      ],
      modules: [
        { code: 'sales', label: 'Ventas', available: true, status: 'OPERATIVE' as const, route: '/app/sales' },
        {
          code: 'administration',
          label: 'Administración',
          available: true,
          status: 'OPERATIVE' as const,
          route: '/app/administration',
        },
      ],
    }),
  );

  beforeEach(async () => {
    getOverview.mockClear();
    membership.set({
      id: 1,
      status: 'ACTIVE',
      company: { id: 3, name: 'Empresa Dashboard' },
      branches: [],
      permissions: ['administration.manage'],
    });

    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        provideRouter([]),
        {
          provide: OrganizationContextService,
          useValue: { selectedMembership: membership.asReadonly() },
        },
        { provide: DashboardService, useValue: { getOverview } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Dashboard);
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads real dashboard indicators for the active company', () => {
    expect(getOverview).toHaveBeenCalledWith(3);
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Ventas de hoy');
    expect(text).toContain('$1.000');
    expect(text).toContain('Clientes activos');
    expect(text).toContain('Venta creada');
    expect(text).toContain('Stock crítico');
    expect(text).not.toContain('Pendiente de conectar');
  });

  it('clears the previous company when the active membership changes', async () => {
    membership.set({
      id: 2,
      status: 'ACTIVE',
      company: { id: 8, name: 'Empresa Nueva' },
      branches: [],
      permissions: [],
    });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(getOverview).toHaveBeenLastCalledWith(8);
  });
});
