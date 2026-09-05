import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { PortalAccountPage } from './portal-account';

describe('PortalAccountPage', () => {
  let fixture: ComponentFixture<PortalAccountPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PortalAccountPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(PortalAccountPage);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('loads account and order history and opens the order detail', () => {
    http.expectOne('/api/organizations/context/').flush({ memberships: [] });
    http.expectOne('/api/portal/account/').flush({ accounts: [{ company: 1, company_name: 'Tienda Norte', customer: 9, customer_name: 'Felipe', email: 'f@example.com', phone: '', address: 'Av. Uno 123', commune: 'Providencia', city: 'Santiago' }] });
    http.expectOne('/api/portal/orders/').flush({ orders: [{ id: 12, company: 1, branch: 2, warehouse: 3, customer: 9, number: 1001, status: 'DELIVERED', notes: '', delivery_address: 'Av. Uno 123', delivery_commune: 'Providencia', delivery_city: 'Santiago', created_at: '2026-09-04T00:00:00Z', updated_at: '2026-09-04T00:00:00Z', items: [{ id: 1, variant: 5, variant_sku: 'CAF-1', product_name: 'Café premium', quantity: '1.000', unit_price: '12990.00', line_total: '12990.00' }], total: '12990.00' }] });
    http.expectOne('/api/portal/payments/mercado-pago/').flush({ payments: [] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Pedido #1001');
    fixture.componentInstance.showDetail(fixture.componentInstance.orders()[0]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Café premium');
    expect(fixture.nativeElement.textContent).toContain('Entregado');
  });
  it('shows management navigation when the person already has a PYME', () => {
    http.expectOne('/api/organizations/context/').flush({
      memberships: [
        {
          id: 10,
          status: 'ACTIVE',
          company: { id: 1, name: 'Tienda Norte' },
          branches: [],
          permissions: [],
        },
      ],
    });
    http.expectOne('/api/portal/account/').flush({ accounts: [] });
    http.expectOne('/api/portal/orders/').flush({ orders: [] });
    http.expectOne('/api/portal/payments/mercado-pago/').flush({ payments: [] });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('También administras una PYME');
    expect(fixture.nativeElement.textContent).toContain('Gestionar mi PYME');
    expect(fixture.nativeElement.textContent).not.toContain('¿También vendes?');
  });

});
