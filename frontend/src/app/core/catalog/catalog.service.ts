import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable } from 'rxjs';

import {
  CatalogProduct,
  CatalogProductCreateInput,
  CatalogProductCreateResponse,
  CatalogProductListResponse,
  CatalogProductOptionsResponse,
} from './catalog.models';

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

  getProductOptions(companyId: number): Observable<CatalogProductOptionsResponse> {
    return this.http.get<CatalogProductOptionsResponse>('/api/catalog/products/options/', {
      params: {
        company: companyId.toString(),
      },
    });
  }

  createProduct(companyId: number, input: CatalogProductCreateInput): Observable<CatalogProduct> {
    return this.http
      .post<CatalogProductCreateResponse>('/api/catalog/products/', {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.product));
  }
}
