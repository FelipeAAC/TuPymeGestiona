import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import {
  Warehouse,
  WarehouseInput,
  WarehouseListResponse,
  WarehouseResponse,
} from './warehouses.models';

@Injectable({
  providedIn: 'root',
})
export class WarehousesService {
  private readonly http = inject(HttpClient);

  listWarehouses(companyId: number): Observable<WarehouseListResponse> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http.get<WarehouseListResponse>('/api/organizations/warehouses/', { params });
  }

  retrieveWarehouse(companyId: number, warehouseId: number): Observable<Warehouse> {
    const params = new HttpParams().set('company', companyId.toString());

    return this.http
      .get<WarehouseResponse>(`/api/organizations/warehouses/${warehouseId}/`, { params })
      .pipe(map((response) => response.warehouse));
  }

  createWarehouse(companyId: number, input: WarehouseInput): Observable<Warehouse> {
    return this.http
      .post<WarehouseResponse>('/api/organizations/warehouses/', {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.warehouse));
  }

  updateWarehouse(
    companyId: number,
    warehouseId: number,
    input: WarehouseInput,
  ): Observable<Warehouse> {
    return this.http
      .patch<WarehouseResponse>(`/api/organizations/warehouses/${warehouseId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.warehouse));
  }
}
