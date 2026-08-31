import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import {
  Supplier,
  SupplierInput,
  SupplierListResponse,
  SupplierResponse,
} from './suppliers.models';

@Injectable({
  providedIn: 'root',
})
export class SuppliersService {
  private readonly http = inject(HttpClient);

  listSuppliers(companyId: number): Observable<SupplierListResponse> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http.get<SupplierListResponse>('/api/catalog/suppliers/', { params });
  }

  retrieveSupplier(companyId: number, supplierId: number): Observable<Supplier> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http
      .get<SupplierResponse>(`/api/catalog/suppliers/${supplierId}/`, { params })
      .pipe(map((response) => response.supplier));
  }

  createSupplier(companyId: number, input: SupplierInput): Observable<Supplier> {
    return this.http
      .post<SupplierResponse>('/api/catalog/suppliers/', {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.supplier));
  }

  updateSupplier(
    companyId: number,
    supplierId: number,
    input: SupplierInput,
  ): Observable<Supplier> {
    return this.http
      .patch<SupplierResponse>(`/api/catalog/suppliers/${supplierId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.supplier));
  }
}
