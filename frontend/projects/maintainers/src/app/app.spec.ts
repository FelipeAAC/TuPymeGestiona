import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { MaintainersApp } from './app';
import { MaintainersApi } from './api.service';
import { AdministrationOverview } from './models';

const overview: AdministrationOverview = {
  company: {
    id: 10,
    name: 'Pyme Demo',
    rut: '76.000.000-0',
    legal_name: 'Pyme Demo SpA',
    business_activity: 'Comercio',
    contact_email: 'admin@demo.cl',
    phone: '',
    address: '',
    commune: '',
    city: '',
    is_active: true,
  },
  branches: [],
  users: [],
  roles: [],
  permissions: [],
  payment_methods: [],
  order_statuses: [],
  settings: {
    vat_rate: '19.00',
    currency: 'CLP',
    timezone: 'America/Santiago',
    payment_provider: 'MERCADO_PAGO',
    payment_sandbox_enabled: true,
    notification_sender_email: 'noreply@demo.cl',
    updated_at: '2026-09-04T00:00:00Z',
  },
  events: [],
};

class ApiMock {
  me = vi.fn(() =>
    of({ id: 1, username: 'admin', email: 'admin@demo.cl', first_name: 'Admin', last_name: '' }),
  );
  context = vi.fn(() =>
    of([
      {
        id: 100,
        status: 'ACTIVE' as const,
        company: { id: 10, name: 'Pyme Demo' },
        branches: [],
        permissions: ['administration.view'],
      },
      {
        id: 200,
        status: 'ACTIVE' as const,
        company: { id: 20, name: 'Otra Pyme' },
        branches: [],
        permissions: ['administration.view'],
      },
    ]),
  );
  overview = vi.fn(() => of(overview));
  catalog = vi.fn(() => of({ categories: [], products: [], brands: [] }));
  directories = vi.fn(() => of({ suppliers: [], warehouses: [] }));
  login = vi.fn(() =>
    of({ id: 1, username: 'admin', email: '', first_name: '', last_name: '' }),
  );
  logout = vi.fn(() => of({}));
}

describe('MaintainersApp secondary application', () => {
  let api: ApiMock;

  beforeEach(async () => {
    api = new ApiMock();
    await TestBed.configureTestingModule({
      imports: [MaintainersApp],
      providers: [{ provide: MaintainersApi, useValue: api }],
    }).compileComponents();
  });

  it('restores the shared session and loads the first company from the backend', () => {
    const fixture = TestBed.createComponent(MaintainersApp);
    fixture.detectChanges();

    expect(api.me).toHaveBeenCalled();
    expect(api.context).toHaveBeenCalled();
    expect(api.overview).toHaveBeenCalledWith(10);
    expect(fixture.componentInstance.activeCompanyName()).toBe('Pyme Demo');
  });

  it('switches company context without inventing a tenant locally', () => {
    const fixture = TestBed.createComponent(MaintainersApp);
    fixture.detectChanges();

    fixture.componentInstance.selectMembership(200);

    expect(api.overview).toHaveBeenLastCalledWith(20);
    expect(fixture.componentInstance.activeCompanyId()).toBe(20);
  });

  it('keeps administration permission failures visible to the user', () => {
    api.overview.mockReturnValueOnce(
      throwError(() => ({ error: { detail: 'No tiene permisos de administración.' } })),
    );

    const fixture = TestBed.createComponent(MaintainersApp);
    fixture.detectChanges();

    expect(fixture.componentInstance.error()).toContain('permisos');
  });
});
