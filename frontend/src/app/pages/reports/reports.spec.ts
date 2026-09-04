import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { ReportsService } from '../../core/reports/reports.service';
import { Reports } from './reports';

describe('Reports', () => {
  let fixture: ComponentFixture<Reports>;
  const membership = signal<OrganizationMembership | null>({
    id: 1,
    status: 'ACTIVE',
    company: { id: 3, name: 'Empresa Reportes' },
    branches: [],
    permissions: ['administration.manage', 'inventory.stocks.manage'],
  });

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Reports],
      providers: [
        {
          provide: OrganizationContextService,
          useValue: { selectedMembership: membership.asReadonly() },
        },
        {
          provide: ReportsService,
          useValue: {
            getOptions: vi.fn(() => of({
              company: { id: 3, name: 'Empresa Reportes' },
              permissions: { sales: true, inventory: true },
              branches: [], sellers: [], warehouses: [], categories: [],
            })),
            getSalesReport: vi.fn(() => of({
              filters: { date_from: 'Sin límite', date_to: 'Sin límite', branch: 'Todas', seller: 'Todos' },
              summary: { records: 1, active_sales: 1, gross_total: '1000.00', paid_total: '1000.00', balance_total: '0.00' },
              rows: [{ id: 1, number: 1, date: '2026-09-03', branch: 'Matriz', branch_code: 'M', seller: 'admin', seller_username: 'admin', customer: 'Cliente', customer_code: 'C1', status: 'PAID', total_amount: '1000.00', paid_amount: '1000.00', balance: '0.00' }],
            })),
            getInventoryReport: vi.fn(() => of({
              filters: { warehouse: 'Todas', category: 'Todas', stock_level: 'Todos', critical_threshold: '5.000' },
              summary: { records: 0, total_units: '0.000', reference_value: '0.00', critical_count: 0, out_count: 0, critical_threshold: '5.000' },
              valuation_note: 'Nota', rows: [],
            })),
            downloadSales: vi.fn(),
            downloadInventory: vi.fn(),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Reports);
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads the sales report for the active company', () => {
    expect(fixture.nativeElement.textContent).toContain('Reporte de ventas');
    expect(fixture.nativeElement.textContent).toContain('Cliente');
    expect(fixture.nativeElement.textContent).toContain('Exportar PDF');
  });

  it('can switch to inventory report', () => {
    fixture.componentInstance.selectTab('inventory');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Reporte de inventario');
  });
});
