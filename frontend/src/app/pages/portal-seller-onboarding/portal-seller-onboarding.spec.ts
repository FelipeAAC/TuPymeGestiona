import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { PortalSellerOnboarding } from './portal-seller-onboarding';

describe('PortalSellerOnboarding', () => {
  let http: HttpTestingController;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PortalSellerOnboarding],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => http.verify());

  it('creates a company for the current person and switches to its management context', () => {
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(PortalSellerOnboarding);

    fixture.componentInstance.form.setValue({
      name: 'Mi Pyme',
      rut: '12.345.678-5',
      legalName: 'Mi Pyme SpA',
      businessActivity: 'Comercio',
      contactEmail: 'propietario@example.com',
      phone: '',
      address: 'Av. Uno 123',
      commune: 'Providencia',
      city: 'Santiago',
    });
    fixture.componentInstance.submit();

    const create = http.expectOne('/api/administration/self-service/companies/');
    expect(create.request.method).toBe('POST');
    create.flush({
      company: {
        id: 44,
        name: 'Mi Pyme',
        rut: '12345678-5',
        legal_name: 'Mi Pyme SpA',
        business_activity: 'Comercio',
        contact_email: 'propietario@example.com',
        phone: '',
        address: 'Av. Uno 123',
        commune: 'Providencia',
        city: 'Santiago',
        is_active: true,
      },
    });

    http.expectOne('/api/organizations/context/').flush({
      memberships: [
        {
          id: 55,
          status: 'ACTIVE',
          company: { id: 44, name: 'Mi Pyme' },
          branches: [{ id: 66, code: 'CASA', name: 'Casa Matriz' }],
          permissions: ['administration.manage'],
        },
      ],
    });

    expect(navigate).toHaveBeenCalledWith(['/app/dashboard']);
  });
});
