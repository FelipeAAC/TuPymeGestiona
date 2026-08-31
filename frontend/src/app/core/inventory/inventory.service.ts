import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import {
  InventoryMovement,
  InventoryMovementCreateResponse,
  InventoryMovementInput,
  InventoryMovementListResponse,
  InventoryMovementQuery,
  InventoryOptionsResponse,
  InventoryStock,
  InventoryStockListResponse,
  InventoryTransfer,
  InventoryTransferCreateResponse,
  InventoryTransferInput,
  InventoryTransferListResponse,
} from './inventory.models';

@Injectable({
  providedIn: 'root',
})
export class InventoryService {
  private readonly http = inject(HttpClient);

  getOptions(companyId: number): Observable<InventoryOptionsResponse> {
    return this.http.get<InventoryOptionsResponse>('/api/inventory/options/', {
      params: {
        company: companyId.toString(),
      },
    });
  }

  listStocks(companyId: number): Observable<InventoryStock[]> {
    return this.http
      .get<InventoryStockListResponse>('/api/inventory/stocks/', {
        params: {
          company: companyId.toString(),
        },
      })
      .pipe(map((response) => response.stocks));
  }

  listMovements(
    companyId: number,
    query: InventoryMovementQuery = {},
  ): Observable<InventoryMovement[]> {
    let params = new HttpParams().set('company', companyId.toString());

    if (query.warehouse) {
      params = params.set('warehouse', query.warehouse.toString());
    }

    if (query.variant) {
      params = params.set('variant', query.variant.toString());
    }

    if (query.movement_type) {
      params = params.set('movement_type', query.movement_type);
    }

    return this.http
      .get<InventoryMovementListResponse>('/api/inventory/movements/', { params })
      .pipe(map((response) => response.movements));
  }

  createMovement(
    companyId: number,
    input: InventoryMovementInput,
  ): Observable<InventoryMovementCreateResponse> {
    return this.http.post<InventoryMovementCreateResponse>('/api/inventory/movements/', {
      company: companyId,
      ...input,
    });
  }

  listTransfers(companyId: number): Observable<InventoryTransfer[]> {
    return this.http
      .get<InventoryTransferListResponse>('/api/inventory/transfers/', {
        params: {
          company: companyId.toString(),
        },
      })
      .pipe(map((response) => response.transfers));
  }

  createTransfer(companyId: number, input: InventoryTransferInput): Observable<InventoryTransfer> {
    return this.http
      .post<InventoryTransferCreateResponse>('/api/inventory/transfers/', {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.transfer));
  }
}
