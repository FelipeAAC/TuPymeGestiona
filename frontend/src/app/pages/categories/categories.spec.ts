import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { CatalogCategoryDetail } from '../../core/catalog/catalog.models';
import { CatalogService } from '../../core/catalog/catalog.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { Categories } from './categories';

describe('Categories', () => {
  let component: Categories;
  let fixture: ComponentFixture<Categories>;
  const membership: OrganizationMembership = {
    id: 2, status: 'ACTIVE', company: { id: 7, name: 'Comercial Andina SpA' }, branches: [],
  };
  const active: CatalogCategoryDetail = { id: 10, name: 'Vestuario', parent: null, status: 'ACTIVE' };
  const inactive: CatalogCategoryDetail = { id: 11, name: 'Temporada', parent: null, status: 'INACTIVE' };
  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const catalogService = {
    listCategories: vi.fn(() => of([active, inactive])),
    createCategory: vi.fn(() => of(active)),
    updateCategory: vi.fn((_company: number, id: number, input: object) =>
      of({ ...(id === 10 ? active : inactive), ...input } as CatalogCategoryDetail),
    ),
  };

  beforeEach(async () => {
    Object.values(catalogService).forEach((mock) => mock.mockClear());
    selectedMembership.set(membership);
    await TestBed.configureTestingModule({
      imports: [Categories],
      providers: [
        { provide: CatalogService, useValue: catalogService },
        { provide: OrganizationContextService, useValue: { selectedMembership: selectedMembership.asReadonly() } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Categories);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads categories including their operational status', () => {
    expect(catalogService.listCategories).toHaveBeenCalledWith(7);
    expect(component.categories()).toEqual([active, inactive]);
    expect(fixture.nativeElement.textContent).toContain('Inactiva');
  });

  it('creates a category and reloads the directory', () => {
    component.createForm.setValue({ name: 'Vestuario', parentId: 0 });
    component.onSubmit();
    expect(catalogService.createCategory).toHaveBeenCalledWith(7, { name: 'Vestuario', parent: null });
    expect(catalogService.listCategories).toHaveBeenCalledTimes(2);
  });

  it('updates and disables an existing category', () => {
    component.openEditor(active);
    component.editForm.setValue({ name: 'Vestuario actualizado', parentId: 0, status: 'INACTIVE' });
    component.saveCategory();
    expect(catalogService.updateCategory).toHaveBeenCalledWith(7, 10, {
      name: 'Vestuario actualizado', parent: null, status: 'INACTIVE',
    });
  });
});
