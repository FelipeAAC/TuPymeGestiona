import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ReportsService } from './reports.service';

describe('ReportsService', () => {
  let service: ReportsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ReportsService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ReportsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads report options for the active company', () => {
    service.getOptions(3).subscribe();
    const request = http.expectOne((req) => req.url === '/api/reports/options/');
    expect(request.request.params.get('company')).toBe('3');
    request.flush({ company: { id: 3, name: 'Empresa' }, permissions: { sales: true, inventory: true }, branches: [], sellers: [], warehouses: [], categories: [] });
  });

  it('sends sales filters', () => {
    service.getSalesReport(3, { date_from: '2026-09-01', branch: 2, seller: 8 }).subscribe();
    const request = http.expectOne((req) => req.url === '/api/reports/sales/');
    expect(request.request.params.get('date_from')).toBe('2026-09-01');
    expect(request.request.params.get('branch')).toBe('2');
    expect(request.request.params.get('seller')).toBe('8');
    request.flush({ filters: {}, summary: {}, rows: [] });
  });

  it('requests inventory export as blob', () => {
    service.downloadInventory(5, { stock_level: 'CRITICAL', critical_threshold: 7 }, 'xls').subscribe();
    const request = http.expectOne((req) => req.url === '/api/reports/inventory/export/xls/');
    expect(request.request.responseType).toBe('blob');
    expect(request.request.params.get('critical_threshold')).toBe('7');
    request.flush(new Blob(['xlsx']));
  });
});
