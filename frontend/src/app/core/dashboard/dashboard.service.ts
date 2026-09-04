import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { DashboardOverviewResponse } from './dashboard.models';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  getOverview(companyId: number): Observable<DashboardOverviewResponse> {
    return this.http.get<DashboardOverviewResponse>('/api/dashboard/overview/', {
      params: new HttpParams().set('company', companyId.toString()),
    });
  }
}
