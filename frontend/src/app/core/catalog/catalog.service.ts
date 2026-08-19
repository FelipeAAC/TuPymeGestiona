import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable } from 'rxjs';

import {
  CatalogBrand,
  CatalogBrandCreateInput,
  CatalogBrandCreateResponse,
  CatalogBrandListResponse,
  CatalogCategoryCreateInput,
  CatalogCategoryCreateResponse,
  CatalogCategoryDetail,
  CatalogCategoryListResponse,
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

  listCategories(companyId: number): Observable<CatalogCategoryDetail[]> {
    return this.http
      .get<CatalogCategoryListResponse>('/api/catalog/categories/', {
        params: {
          company: companyId.toString(),
        },
      })
      .pipe(map((response) => response.categories));
  }

  createCategory(
    companyId: number,
    input: CatalogCategoryCreateInput,
  ): Observable<CatalogCategoryDetail> {
    return this.http
      .post<CatalogCategoryCreateResponse>('/api/catalog/categories/', {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.category));
  }

  listBrands(companyId: number): Observable<CatalogBrand[]> {
    return this.http
      .get<CatalogBrandListResponse>('/api/catalog/brands/', {
        params: {
          company: companyId.toString(),
        },
      })
      .pipe(map((response) => response.brands));
  }

  createBrand(companyId: number, input: CatalogBrandCreateInput): Observable<CatalogBrand> {
    return this.http
      .post<CatalogBrandCreateResponse>('/api/catalog/brands/', {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.brand));
  }
}
