import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { PortalProduct } from '../../core/portal/portal.models';
import { Portal } from './portal';

describe('Portal', () => {
  let fixture: ComponentFixture<Portal>;
  let http: HttpTestingController;
  const store = { id: 1, name: 'Tienda Norte', legal_name: '', business_activity: 'Comercio', commune: 'Providencia', city: 'Santiago', branches: [{ id: 2, code: 'CASA', name: 'Casa Matriz', address: '', commune: '', city: '' }] };
  const product: PortalProduct = { id: 4, name: 'Café premium', description: 'Origen nacional', image_url: '', category: { id: 3, name: 'Café' }, brand: null, available: true, variants: [{ id: 5, sku: 'CAF-1', gtin: '', base_price: '12990.00', available_quantity: '3.000', available: true }] };

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

  function flushCatalog(): void {
    http.expectOne('/api/portal/stores/').flush({ stores: [store] });
    http.expectOne('/api/portal/stores/1/catalog/').flush({
      store: { id: 1, name: 'Tienda Norte', business_activity: 'Comercio' },
      categories: [{ id: 3, name: 'Café' }],
      products: [product],
    });
    fixture.detectChanges();
  }

  it('loads stores and renders the published catalog', () => {
    flushCatalog();
    expect(fixture.nativeElement.textContent).toContain('Tienda Norte');
    expect(fixture.nativeElement.textContent).toContain('Café premium');
  });

  it('loads the dedicated product detail required by CU019', () => {
    flushCatalog();
    fixture.componentInstance.openProduct(product);
    http.expectOne('/api/portal/stores/1/products/4/').flush({ product: { ...product, description: 'Detalle completo del producto' } });
    fixture.detectChanges();
    expect(fixture.componentInstance.selectedProduct()?.description).toBe('Detalle completo del producto');
    expect(fixture.nativeElement.textContent).toContain('Detalle completo del producto');
  });
});
