import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { map, Observable } from 'rxjs';

import {
  AdminBranch,
  AdminCompany,
  AdminCompanySettings,
  AdminOrderStatus,
  AdminPaymentMethod,
  AdminRole,
  AdminUser,
  AdministrationOverview,
} from './administration.models';

@Injectable({ providedIn: 'root' })
export class AdministrationService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/administration';

  loadOverview(companyId: number): Observable<AdministrationOverview> {
    return this.http.get<AdministrationOverview>(`${this.baseUrl}/overview/`, {
      params: new HttpParams().set('company', companyId),
    });
  }

  createCompany(input: Partial<AdminCompany>): Observable<AdminCompany> {
    return this.http
      .post<{ company: AdminCompany }>(`${this.baseUrl}/companies/`, input)
      .pipe(map((response) => response.company));
  }

  createOwnCompany(input: Partial<AdminCompany>): Observable<AdminCompany> {
    return this.http
      .post<{ company: AdminCompany }>(`${this.baseUrl}/self-service/companies/`, input)
      .pipe(map((response) => response.company));
  }

  updateCompany(companyId: number, input: Partial<AdminCompany>): Observable<AdminCompany> {
    return this.http
      .patch<{ company: AdminCompany }>(`${this.baseUrl}/companies/${companyId}/`, input)
      .pipe(map((response) => response.company));
  }

  createBranch(companyId: number, input: Partial<AdminBranch>): Observable<AdminBranch> {
    return this.http
      .post<{ branch: AdminBranch }>(`${this.baseUrl}/branches/`, { company: companyId, ...input })
      .pipe(map((response) => response.branch));
  }

  updateBranch(companyId: number, branchId: number, input: Partial<AdminBranch>): Observable<AdminBranch> {
    return this.http
      .patch<{ branch: AdminBranch }>(`${this.baseUrl}/branches/${branchId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.branch));
  }

  createUser(companyId: number, input: Record<string, unknown>): Observable<AdminUser> {
    return this.http
      .post<{ user: AdminUser }>(`${this.baseUrl}/users/`, { company: companyId, ...input })
      .pipe(map((response) => response.user));
  }

  updateUser(companyId: number, membershipId: number, input: Record<string, unknown>): Observable<AdminUser> {
    return this.http
      .patch<{ user: AdminUser }>(`${this.baseUrl}/users/${membershipId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.user));
  }

  createRole(companyId: number, input: Record<string, unknown>): Observable<AdminRole> {
    return this.http
      .post<{ role: AdminRole }>(`${this.baseUrl}/roles/`, { company: companyId, ...input })
      .pipe(map((response) => response.role));
  }

  updateRole(companyId: number, roleId: number, input: Record<string, unknown>): Observable<AdminRole> {
    return this.http
      .patch<{ role: AdminRole }>(`${this.baseUrl}/roles/${roleId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.role));
  }

  createPaymentMethod(companyId: number, input: Partial<AdminPaymentMethod>): Observable<AdminPaymentMethod> {
    return this.http
      .post<{ payment_method: AdminPaymentMethod }>(`${this.baseUrl}/payment-methods/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.payment_method));
  }

  updatePaymentMethod(companyId: number, methodId: number, input: Partial<AdminPaymentMethod>): Observable<AdminPaymentMethod> {
    return this.http
      .patch<{ payment_method: AdminPaymentMethod }>(`${this.baseUrl}/payment-methods/${methodId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.payment_method));
  }

  updateOrderStatus(companyId: number, statusId: number, input: Partial<AdminOrderStatus>): Observable<AdminOrderStatus> {
    return this.http
      .patch<{ order_status: AdminOrderStatus }>(`${this.baseUrl}/order-statuses/${statusId}/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.order_status));
  }

  updateSettings(companyId: number, input: Partial<AdminCompanySettings>): Observable<AdminCompanySettings> {
    return this.http
      .patch<{ settings: AdminCompanySettings }>(`${this.baseUrl}/settings/`, {
        company: companyId,
        ...input,
      })
      .pipe(map((response) => response.settings));
  }
}
