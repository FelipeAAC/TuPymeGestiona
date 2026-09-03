import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { PortalService } from './portal.service';


describe('PortalService', () => {
  let service: PortalService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(PortalService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads public stores and catalog filters', () => {
    service.listStores().subscribe((stores) => expect(stores[0].name).toBe('Tienda'));
    const stores = http.expectOne('/api/portal/stores/');
    stores.flush({ stores: [{ id: 1, name: 'Tienda', legal_name: '', business_activity: '', commune: '', city: '', branches: [] }] });

    service.getCatalog(1, ' café ', 8).subscribe();
    const catalog = http.expectOne((request) => request.url === '/api/portal/stores/1/catalog/');
    expect(catalog.request.params.get('search')).toBe('café');
    expect(catalog.request.params.get('category')).toBe('8');
    catalog.flush({ store: { id: 1, name: 'Tienda', business_activity: '' }, categories: [], products: [] });
  });

  it('registers through csrf and creates orders with an idempotency key', () => {
    const registration = {
      company: 1, email: 'cliente@example.com', password: 'Clave-segura-2026!', first_name: 'Ana', last_name: '', phone: '', address: 'Uno 1', commune: 'Santiago', city: 'Santiago',
    };
    service.register(registration).subscribe();
    http.expectOne('/api/auth/csrf/').flush({ detail: 'ok' });
    const register = http.expectOne('/api/portal/register/');
    expect(register.request.body).toEqual(registration);
    register.flush({ account: { company: 1 } });

    service.createOrder({ company: 1, branch: 2, delivery_address: 'Uno 1', delivery_commune: 'Santiago', delivery_city: 'Santiago', notes: '', items: [{ variant: 4, quantity: '1.000' }] }, 'order-key').subscribe();
    const order = http.expectOne('/api/portal/orders/create/');
    expect(order.request.headers.get('Idempotency-Key')).toBe('order-key');
    order.flush({ order: { id: 9 } });
  });
  it('creates and refreshes Mercado Pago checkouts through the backend', () => {
    service.createMercadoPagoPreference(9, 'mp-key').subscribe((payment) =>
      expect(payment.status).toBe('READY'),
    );
    const preference = http.expectOne('/api/portal/payments/orders/9/mercado-pago/preference/');
    expect(preference.request.headers.get('Idempotency-Key')).toBe('mp-key');
    preference.flush({ payment: { id: 1, order: 9, status: 'READY', amount: '1000.00', currency: 'CLP', preference_id: 'PREF', checkout_url: 'https://mp.test', provider_status: '', provider_status_detail: '', last_payment_id: '', updated_at: '', sale: null } });

    service.refreshMercadoPagoPayment(9, 'PAY-1').subscribe((payment) =>
      expect(payment.status).toBe('APPROVED'),
    );
    const refresh = http.expectOne('/api/portal/payments/orders/9/mercado-pago/refresh/');
    expect(refresh.request.body).toEqual({ payment_id: 'PAY-1' });
    refresh.flush({ payment: { id: 1, order: 9, status: 'APPROVED', amount: '1000.00', currency: 'CLP', preference_id: 'PREF', checkout_url: 'https://mp.test', provider_status: 'approved', provider_status_detail: 'accredited', last_payment_id: 'PAY-1', updated_at: '', sale: null } });
  });

});
