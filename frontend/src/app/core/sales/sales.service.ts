import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import {
  Sale,
  SaleCancelResponse,
  SaleCreateResponse,
  SaleListQuery,
  SaleListResponse,
  SaleOptionsResponse,
  SalePaymentResponse,
  SaleResponse,
} from './sales.models';

@Injectable({
  providedIn: 'root',
})
export class SalesService {
  private readonly http = inject(HttpClient);

  getOptions(companyId: number): Observable<SaleOptionsResponse> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http.get<SaleOptionsResponse>('/api/sales/options/', { params });
  }

  listSales(companyId: number, query: SaleListQuery = {}): Observable<SaleListResponse> {
    let params = new HttpParams().set('company', companyId.toString());

    if (query.status) {
      params = params.set('status', query.status);
    }

    if (query.branch) {
      params = params.set('branch', query.branch.toString());
    }

    if (query.customer) {
      params = params.set('customer', query.customer.toString());
    }

    if (query.search?.trim()) {
      params = params.set('search', query.search.trim());
    }

    params = params
      .set('ordering', query.ordering || '-number')
      .set('page', (query.page || 1).toString())
      .set('page_size', (query.page_size || 20).toString());

    return this.http.get<SaleListResponse>('/api/sales/', { params });
  }

  retrieveSale(companyId: number, saleId: number): Observable<Sale> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http
      .get<SaleResponse>(`/api/sales/${saleId}/`, { params })
      .pipe(map((response) => response.sale));
  }

  createSale(
    companyId: number,
    orderId: number,
    idempotencyKey: string,
  ): Observable<SaleCreateResponse> {
    return this.http.post<SaleCreateResponse>('/api/sales/', {
      company: companyId,
      order: orderId,
      idempotency_key: idempotencyKey,
    });
  }

  recordPayment(
    companyId: number,
    saleId: number,
    amount: number,
    reference: string,
    idempotencyKey: string,
  ): Observable<SalePaymentResponse> {
    return this.http.post<SalePaymentResponse>(`/api/sales/${saleId}/payments/`, {
      company: companyId,
      amount,
      reference,
      idempotency_key: idempotencyKey,
    });
  }

  cancelSale(companyId: number, saleId: number): Observable<SaleCancelResponse> {
    return this.http.post<SaleCancelResponse>(`/api/sales/${saleId}/cancel/`, {
      company: companyId,
    });
  }
}
