import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import {
  Customer,
  CustomerInput,
  CustomerListQuery,
  CustomerListResponse,
  CustomerResponse,
} from './customers.models';

@Injectable({
  providedIn: 'root',
})
export class CustomersService {
  private readonly http = inject(HttpClient);

  listCustomers(companyId: number, query: CustomerListQuery): Observable<CustomerListResponse> {
    let params = new HttpParams()
      .set('company', companyId.toString())
      .set('ordering', query.ordering)
      .set('page', query.page.toString())
      .set('page_size', query.page_size.toString());

    if (query.search) {
      params = params.set('search', query.search);
    }

    if (query.status) {
      params = params.set('status', query.status);
    }

    return this.http.get<CustomerListResponse>('/api/customers/', { params });
  }

  createCustomer(companyId: number, input: CustomerInput): Observable<Customer> {
    return this.http
      .post<CustomerResponse>('/api/customers/', {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.customer));
  }

  updateCustomer(
    companyId: number,
    customerId: number,
    input: CustomerInput,
  ): Observable<Customer> {
    return this.http
      .patch<CustomerResponse>(`/api/customers/${customerId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.customer));
  }
}
