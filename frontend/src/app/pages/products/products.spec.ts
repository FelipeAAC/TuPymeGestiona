import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { CatalogProduct } from '../../core/catalog/catalog.models';
import { CatalogService } from '../../core/catalog/catalog.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { Products } from './products';

describe('Products', () => {
  let component: Products;
  let fixture: ComponentFixture<Products>;
  const membership: OrganizationMembership = { id: 2, status: 'ACTIVE', company: { id: 7, name: 'Comercial Andina SpA' }, branches: [] };
  const product: CatalogProduct = {
    id: 20, name: 'Polera', description: 'Algodón', image_url: '', status: 'ACTIVE',
    category: { id: 3, name: 'Vestuario' }, brand: { id: 4, name: 'Andina' },
    variants: [{ id: 30, sku: 'POL-1', gtin: '', base_price: '12990.00', status: 'ACTIVE' }],
  };
  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const catalogService = {
    listProducts: vi.fn(() => of([product])),
    getProductOptions: vi.fn(() => of({ categories: [{ id: 3, name: 'Vestuario' }], brands: [{ id: 4, name: 'Andina' }] })),
    createProduct: vi.fn(() => of(product)),
    updateProduct: vi.fn((_company: number, _id: number, input: object) => of({ ...product, ...input } as CatalogProduct)),
  };

  beforeEach(async () => {
    Object.values(catalogService).forEach((mock) => mock.mockClear());
    selectedMembership.set(membership);
    await TestBed.configureTestingModule({
      imports: [Products],
      providers: [
        { provide: CatalogService, useValue: catalogService },
        { provide: OrganizationContextService, useValue: { selectedMembership: selectedMembership.asReadonly() } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Products);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads products and management options', () => {
    expect(catalogService.listProducts).toHaveBeenCalledWith(7);
    expect(catalogService.getProductOptions).toHaveBeenCalledWith(7);
    expect(fixture.nativeElement.textContent).toContain('Polera');
  });

  it('updates an existing product from the Angular editor', () => {
    component.openEditor(product);
    component.editForm.patchValue({ name: 'Polera premium', status: 'ACTIVE' });
    component.saveProduct();
    expect(catalogService.updateProduct).toHaveBeenCalledWith(7, 20, {
      name: 'Polera premium', description: 'Algodón', image_url: '', category: 3, brand: 4, status: 'ACTIVE',
    });
  });

  it('disables a product without deleting it', () => {
    component.setProductStatus(product, 'INACTIVE');
    expect(catalogService.updateProduct).toHaveBeenCalledWith(7, 20, { status: 'INACTIVE' });
  });
});
