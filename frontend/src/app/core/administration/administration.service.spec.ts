import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';

import { AdministrationService } from './administration.service';


describe('AdministrationService', () => {
  let service: AdministrationService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AdministrationService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AdministrationService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the administration overview scoped to company', () => {
    service.loadOverview(7).subscribe();
    const request = http.expectOne((item) => item.url === '/api/administration/overview/' && item.params.get('company') === '7');
    expect(request.request.method).toBe('GET');
    request.flush({ company: {}, branches: [], users: [], roles: [], permissions: [], payment_methods: [], order_statuses: [], settings: {}, events: [] });
  });


  it('creates a company without embedding secrets', () => {
    service.createCompany({ name: 'Nueva Empresa', rut: '12345678-5' }).subscribe();
    const request = http.expectOne('/api/administration/companies/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.name).toBe('Nueva Empresa');
    request.flush({ company: {} });
  });

  it('creates a user with the selected company', () => {
    service.createUser(3, { email: 'user@example.com', role_ids: [], branch_ids: [] }).subscribe();
    const request = http.expectOne('/api/administration/users/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.company).toBe(3);
    request.flush({ user: {} });
  });

  it('updates a role without exposing another company endpoint', () => {
    service.updateRole(4, 11, { name: 'Supervisor', permission_codes: [] }).subscribe();
    const request = http.expectOne('/api/administration/roles/11/');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body.company).toBe(4);
    request.flush({ role: {} });
  });

  it('updates company settings through the non-secret settings endpoint', () => {
    service.updateSettings(9, { vat_rate: '19.00' }).subscribe();
    const request = http.expectOne('/api/administration/settings/');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ company: 9, vat_rate: '19.00' });
    request.flush({ settings: {} });
  });
});
