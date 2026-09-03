import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable, switchMap } from 'rxjs';

import {
  PortalAccount,
  PortalCatalogResponse,
  PortalOrder,
  PortalOrderInput,
  PortalProduct,
  PortalRegistrationInput,
  PortalStore,
} from './portal.models';

@Injectable({ providedIn: 'root' })
export class PortalService {
  private readonly http = inject(HttpClient);

  listStores(): Observable<PortalStore[]> {
    return this.http
      .get<{ stores: PortalStore[] }>('/api/portal/stores/')
      .pipe(map((response) => response.stores));
  }

  getCatalog(companyId: number, search = '', categoryId = 0): Observable<PortalCatalogResponse> {
    let params = new HttpParams();
    if (search.trim()) params = params.set('search', search.trim());
    if (categoryId > 0) params = params.set('category', categoryId.toString());
    return this.http.get<PortalCatalogResponse>(`/api/portal/stores/${companyId}/catalog/`, {
      params,
    });
  }

  getProduct(companyId: number, productId: number): Observable<PortalProduct> {
    return this.http
      .get<{ product: PortalProduct }>(
        `/api/portal/stores/${companyId}/products/${productId}/`,
      )
      .pipe(map((response) => response.product));
  }

  register(input: PortalRegistrationInput): Observable<{ account: { company: number } }> {
    return this.http.get('/api/auth/csrf/').pipe(
      switchMap(() =>
        this.http.post<{ account: { company: number } }>('/api/portal/register/', input),
      ),
    );
  }

  getAccounts(): Observable<PortalAccount[]> {
    return this.http
      .get<{ accounts: PortalAccount[] }>('/api/portal/account/')
      .pipe(map((response) => response.accounts));
  }

  getOrders(companyId?: number): Observable<PortalOrder[]> {
    let params = new HttpParams();
    if (companyId) params = params.set('company', companyId.toString());
    return this.http
      .get<{ orders: PortalOrder[] }>('/api/portal/orders/', { params })
      .pipe(map((response) => response.orders));
  }

  getOrder(orderId: number): Observable<PortalOrder> {
    return this.http
      .get<{ order: PortalOrder }>(`/api/portal/orders/${orderId}/`)
      .pipe(map((response) => response.order));
  }

  createOrder(input: PortalOrderInput, idempotencyKey: string): Observable<PortalOrder> {
    const headers = new HttpHeaders().set('Idempotency-Key', idempotencyKey);
    return this.http
      .post<{ order: PortalOrder }>('/api/portal/orders/create/', input, { headers })
      .pipe(map((response) => response.order));
  }
}
