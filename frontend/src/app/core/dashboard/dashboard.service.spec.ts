import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { DashboardService } from './dashboard.service';

describe('DashboardService', () => {
  let service: DashboardService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [DashboardService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DashboardService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the dashboard overview for the active company', () => {
    service.getOverview(3).subscribe();

    const request = http.expectOne((req) => req.url === '/api/dashboard/overview/');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('company')).toBe('3');
    request.flush({
      company: { id: 3, name: 'Empresa' },
      generated_at: '2026-09-04T00:00:00-04:00',
      permissions: {
        sales: true, orders: true, inventory: true, customers: true, reports: true, administration: true,
      },
      metrics: {
        sales_today_amount: '1000.00', sales_today_count: 1, pending_orders: 2, low_stock: 1,
        critical_stock: 1, out_of_stock: 0, active_customers: 4,
      },
      alerts: [],
      activity: [],
      modules: [],
    });
  });
});
