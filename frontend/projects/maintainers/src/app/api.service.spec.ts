import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { MaintainersApi } from './api.service';

describe('MaintainersApi', () => {
  let api: MaintainersApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [MaintainersApi, provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(MaintainersApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads organization context from the shared backend', () => {
    api.context().subscribe((memberships) => expect(memberships[0].company.id).toBe(7));

    const request = http.expectOne('/api/organizations/context/');
    expect(request.request.method).toBe('GET');
    request.flush({
      memberships: [
        {
          id: 1,
          status: 'ACTIVE',
          company: { id: 7, name: 'Pyme' },
          branches: [],
          permissions: [],
        },
      ],
    });
  });

  it('loads administration overview in company scope', () => {
    api.overview(7).subscribe();

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/administration/overview/' &&
        candidate.params.get('company') === '7',
    );
    expect(request.request.method).toBe('GET');
    request.flush({});
  });

  it('updates a category through the existing catalog contract', () => {
    api.updateCategory(7, 12, { status: 'INACTIVE' }).subscribe();

    const request = http.expectOne('/api/catalog/categories/12/');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ company: 7, status: 'INACTIVE' });
    request.flush({
      category: { id: 12, name: 'Categoría', parent: null, status: 'INACTIVE' },
    });
  });
});
