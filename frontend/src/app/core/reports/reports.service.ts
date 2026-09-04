import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  InventoryReportQuery,
  InventoryReportResponse,
  ReportOptionsResponse,
  SalesReportQuery,
  SalesReportResponse,
} from './reports.models';

@Injectable({ providedIn: 'root' })
export class ReportsService {
  private readonly http = inject(HttpClient);

  getOptions(companyId: number): Observable<ReportOptionsResponse> {
    return this.http.get<ReportOptionsResponse>('/api/reports/options/', {
      params: new HttpParams().set('company', companyId.toString()),
    });
  }

  getSalesReport(companyId: number, query: SalesReportQuery): Observable<SalesReportResponse> {
    return this.http.get<SalesReportResponse>('/api/reports/sales/', {
      params: this.salesParams(companyId, query),
    });
  }

  getInventoryReport(
    companyId: number,
    query: InventoryReportQuery,
  ): Observable<InventoryReportResponse> {
    return this.http.get<InventoryReportResponse>('/api/reports/inventory/', {
      params: this.inventoryParams(companyId, query),
    });
  }

  downloadSales(
    companyId: number,
    query: SalesReportQuery,
    format: 'pdf' | 'xls',
  ): Observable<Blob> {
    return this.http.get(`/api/reports/sales/export/${format}/`, {
      params: this.salesParams(companyId, query),
      responseType: 'blob',
    });
  }

  downloadInventory(
    companyId: number,
    query: InventoryReportQuery,
    format: 'pdf' | 'xls',
  ): Observable<Blob> {
    return this.http.get(`/api/reports/inventory/export/${format}/`, {
      params: this.inventoryParams(companyId, query),
      responseType: 'blob',
    });
  }

  private salesParams(companyId: number, query: SalesReportQuery): HttpParams {
    let params = new HttpParams().set('company', companyId.toString());
    if (query.date_from) params = params.set('date_from', query.date_from);
    if (query.date_to) params = params.set('date_to', query.date_to);
    if (query.branch) params = params.set('branch', query.branch.toString());
    if (query.seller) params = params.set('seller', query.seller.toString());
    return params;
  }

  private inventoryParams(companyId: number, query: InventoryReportQuery): HttpParams {
    let params = new HttpParams().set('company', companyId.toString());
    if (query.warehouse) params = params.set('warehouse', query.warehouse.toString());
    if (query.category) params = params.set('category', query.category.toString());
    if (query.stock_level) params = params.set('stock_level', query.stock_level);
    if (query.critical_threshold !== undefined) {
      params = params.set('critical_threshold', query.critical_threshold.toString());
    }
    return params;
  }
}
