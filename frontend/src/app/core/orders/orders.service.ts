import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import {
  Order,
  OrderInput,
  OrderListQuery,
  OrderListResponse,
  OrderOptionsResponse,
  OrderResponse,
} from './orders.models';

@Injectable({
  providedIn: 'root',
})
export class OrdersService {
  private readonly http = inject(HttpClient);

  getOptions(companyId: number): Observable<OrderOptionsResponse> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http.get<OrderOptionsResponse>('/api/orders/options/', { params });
  }

  listOrders(companyId: number, query: OrderListQuery = {}): Observable<OrderListResponse> {
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

    return this.http.get<OrderListResponse>('/api/orders/', { params });
  }

  retrieveOrder(companyId: number, orderId: number): Observable<Order> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http
      .get<OrderResponse>(`/api/orders/${orderId}/`, { params })
      .pipe(map((response) => response.order));
  }

  createOrder(companyId: number, input: OrderInput): Observable<Order> {
    return this.http
      .post<OrderResponse>('/api/orders/', { company: companyId, ...input })
      .pipe(map((response) => response.order));
  }

  updateOrder(companyId: number, orderId: number, input: OrderInput): Observable<Order> {
    return this.http
      .patch<OrderResponse>(`/api/orders/${orderId}/`, { company: companyId, ...input })
      .pipe(map((response) => response.order));
  }

  confirmOrder(companyId: number, orderId: number): Observable<Order> {
    return this.http
      .post<OrderResponse>(`/api/orders/${orderId}/confirm/`, { company: companyId })
      .pipe(map((response) => response.order));
  }

  cancelOrder(companyId: number, orderId: number): Observable<Order> {
    return this.http
      .post<OrderResponse>(`/api/orders/${orderId}/cancel/`, { company: companyId })
      .pipe(map((response) => response.order));
  }
}
