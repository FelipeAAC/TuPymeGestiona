import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable } from 'rxjs';

import { CatalogProduct, CatalogProductListResponse } from './catalog.models';

@Injectable({
  providedIn: 'root',
})
export class CatalogService {
  private readonly http = inject(HttpClient);

  listProducts(companyId: number): Observable<CatalogProduct[]> {
    return this.http
      .get<CatalogProductListResponse>('/api/catalog/products/', {
        params: {
          company: companyId.toString(),
        },
      })
      .pipe(map((response) => response.products));
  }
}
