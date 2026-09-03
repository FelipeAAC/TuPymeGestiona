import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable, switchMap } from 'rxjs';

import {
  PortalAccount,
  PortalCatalogResponse,
  PortalOrder,
  PortalOrderInput,
  PortalProduct,
  PortalMercadoPagoPayment,
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

  getMercadoPagoPayments(): Observable<PortalMercadoPagoPayment[]> {
    return this.http
      .get<{ payments: PortalMercadoPagoPayment[] }>('/api/portal/payments/mercado-pago/')
      .pipe(map((response) => response.payments));
  }

  getMercadoPagoPayment(orderId: number): Observable<PortalMercadoPagoPayment | null> {
    return this.http
      .get<{ payment: PortalMercadoPagoPayment | null }>(
        `/api/portal/payments/orders/${orderId}/mercado-pago/`,
      )
      .pipe(map((response) => response.payment));
  }

  createMercadoPagoPreference(
    orderId: number,
    idempotencyKey: string,
  ): Observable<PortalMercadoPagoPayment> {
    const headers = new HttpHeaders().set('Idempotency-Key', idempotencyKey);
    return this.http
      .post<{ payment: PortalMercadoPagoPayment }>(
        `/api/portal/payments/orders/${orderId}/mercado-pago/preference/`,
        {},
        { headers },
      )
      .pipe(map((response) => response.payment));
  }

  refreshMercadoPagoPayment(
    orderId: number,
    paymentId: string,
  ): Observable<PortalMercadoPagoPayment> {
    return this.http
      .post<{ payment: PortalMercadoPagoPayment }>(
        `/api/portal/payments/orders/${orderId}/mercado-pago/refresh/`,
        { payment_id: paymentId },
      )
      .pipe(map((response) => response.payment));
  }

  resolveMercadoPagoPreference(orderId: number): Observable<PortalMercadoPagoPayment> {
    return this.http
      .post<{ payment: PortalMercadoPagoPayment }>(
        `/api/portal/payments/orders/${orderId}/mercado-pago/resolve-preference/`,
        {},
      )
      .pipe(map((response) => response.payment));
  }

  createOrder(input: PortalOrderInput, idempotencyKey: string): Observable<PortalOrder> {
    const headers = new HttpHeaders().set('Idempotency-Key', idempotencyKey);
    return this.http
      .post<{ order: PortalOrder }>('/api/portal/orders/create/', input, { headers })
      .pipe(map((response) => response.order));
  }
}
