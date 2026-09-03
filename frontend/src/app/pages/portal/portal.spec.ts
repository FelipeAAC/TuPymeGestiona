import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Portal } from './portal';

describe('Portal', () => {
  let fixture: ComponentFixture<Portal>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Portal],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Portal);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('loads stores and renders the published catalog', () => {
    http.expectOne('/api/portal/stores/').flush({ stores: [{ id: 1, name: 'Tienda Norte', legal_name: '', business_activity: 'Comercio', commune: 'Providencia', city: 'Santiago', branches: [{ id: 2, code: 'CASA', name: 'Casa Matriz', address: '', commune: '', city: '' }] }] });
    http.expectOne('/api/portal/stores/1/catalog/').flush({ store: { id: 1, name: 'Tienda Norte', business_activity: 'Comercio' }, categories: [{ id: 3, name: 'Café' }], products: [{ id: 4, name: 'Café premium', description: 'Origen nacional', image_url: '', category: { id: 3, name: 'Café' }, brand: null, available: true, variants: [{ id: 5, sku: 'CAF-1', gtin: '', base_price: '12990.00', available_quantity: '3.000', available: true }] }] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Tienda Norte');
    expect(fixture.nativeElement.textContent).toContain('Café premium');
  });
});
