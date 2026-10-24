import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable, switchMap } from 'rxjs';

import {
  AdminBranch,
  AdminCompany,
  AdminCompanySettings,
  AdminOrderStatus,
  AdminPaymentMethod,
  AdminRole,
  AdminUser,
  AdministrationOverview,
  AuthUser,
  Brand,
  CatalogState,
  Category,
  CategoryStatus,
  DirectoryState,
  LifecyclePreview,
  MaintainerAuditResponse,
  MaintainerContext,
  Product,
  ProductStatus,
  Supplier,
  Warehouse,
} from './models';

@Injectable({ providedIn: 'root' })
export class MaintainersApi {
  private readonly http = inject(HttpClient);

  private csrfHeaders(): HttpHeaders {
    const token = document.cookie.split('; ').find((entry) => entry.startsWith('csrftoken='))?.split('=')[1] ?? '';
    return token ? new HttpHeaders({ 'X-CSRFToken': decodeURIComponent(token) }) : new HttpHeaders();
  }

  private options() {
    return { headers: this.csrfHeaders(), withCredentials: true };
  }

  csrf(): Observable<unknown> {
    return this.http.get('/api/auth/csrf/', { withCredentials: true });
  }

  me(): Observable<AuthUser> {
    return this.http.get<{ user: AuthUser }>('/api/auth/me/', { withCredentials: true }).pipe(map((response) => response.user));
  }

  login(identifier: string, password: string, rememberMe: boolean): Observable<AuthUser> {
    return this.csrf().pipe(
      switchMap(() => this.http.post<{ user: AuthUser }>('/api/auth/login/', { identifier, password, remember_me: rememberMe }, this.options())),
      map((response) => response.user),
    );
  }

  logout(): Observable<unknown> {
    return this.http.post('/api/auth/logout/', {}, this.options());
  }

  context(): Observable<MaintainerContext> {
    return this.http.get<MaintainerContext>('/api/maintainers/context/', { withCredentials: true });
  }

  audit(filters: Record<string, string> = {}): Observable<MaintainerAuditResponse> {
    let params = new HttpParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params = params.set(key, value);
    });
    return this.http.get<MaintainerAuditResponse>('/api/maintainers/audit/', {
      params,
      withCredentials: true,
    });
  }

  companyOverview(companyId: number): Observable<AdministrationOverview> {
    return this.http.get<AdministrationOverview>(`/api/maintainers/companies/${companyId}/overview/`, { withCredentials: true });
  }

  catalog(companyId: number): Observable<CatalogState> {
    return this.http.get<CatalogState>(`/api/maintainers/companies/${companyId}/catalog/`, { withCredentials: true });
  }

  directories(companyId: number): Observable<DirectoryState> {
    return this.http.get<DirectoryState>(`/api/maintainers/companies/${companyId}/directories/`, { withCredentials: true });
  }

  createCompany(input: Partial<AdminCompany>): Observable<AdminCompany> {
    return this.http.post<{ company: AdminCompany }>('/api/maintainers/companies/', input, this.options()).pipe(map((response) => response.company));
  }

  updateCompany(companyId: number, input: Partial<AdminCompany>): Observable<AdminCompany> {
    return this.http.patch<{ company: AdminCompany }>(`/api/maintainers/companies/${companyId}/`, input, this.options()).pipe(map((response) => response.company));
  }

  createBranch(companyId: number, input: Partial<AdminBranch>): Observable<AdminBranch> {
    return this.http.post<{ branch: AdminBranch }>(`/api/maintainers/companies/${companyId}/branches/`, input, this.options()).pipe(map((response) => response.branch));
  }

  updateBranch(companyId: number, branchId: number, input: Partial<AdminBranch>): Observable<AdminBranch> {
    return this.http.patch<{ branch: AdminBranch }>(`/api/maintainers/companies/${companyId}/branches/${branchId}/`, input, this.options()).pipe(map((response) => response.branch));
  }

  createUser(companyId: number, input: Record<string, unknown>): Observable<AdminUser> {
    return this.http.post<{ user: AdminUser }>(`/api/maintainers/companies/${companyId}/users/`, input, this.options()).pipe(map((response) => response.user));
  }

  updateUser(companyId: number, membershipId: number, input: Record<string, unknown>): Observable<AdminUser> {
    return this.http.patch<{ user: AdminUser }>(`/api/maintainers/companies/${companyId}/users/${membershipId}/`, input, this.options()).pipe(map((response) => response.user));
  }

  revokeUserAccess(companyId: number, membershipId: number): Observable<AdminUser> {
    return this.http.post<{ user: AdminUser }>(`/api/maintainers/companies/${companyId}/users/${membershipId}/revoke/`, {}, this.options()).pipe(map((response) => response.user));
  }

  createRole(companyId: number, input: Record<string, unknown>): Observable<AdminRole> {
    return this.http.post<{ role: AdminRole }>(`/api/maintainers/companies/${companyId}/roles/`, input, this.options()).pipe(map((response) => response.role));
  }

  updateRole(companyId: number, roleId: number, input: Record<string, unknown>): Observable<AdminRole> {
    return this.http.patch<{ role: AdminRole }>(`/api/maintainers/companies/${companyId}/roles/${roleId}/`, input, this.options()).pipe(map((response) => response.role));
  }

  createPaymentMethod(companyId: number, input: Partial<AdminPaymentMethod>): Observable<AdminPaymentMethod> {
    return this.http.post<{ payment_method: AdminPaymentMethod }>(`/api/maintainers/companies/${companyId}/payment-methods/`, input, this.options()).pipe(map((response) => response.payment_method));
  }

  updatePaymentMethod(companyId: number, methodId: number, input: Partial<AdminPaymentMethod>): Observable<AdminPaymentMethod> {
    return this.http.patch<{ payment_method: AdminPaymentMethod }>(`/api/maintainers/companies/${companyId}/payment-methods/${methodId}/`, input, this.options()).pipe(map((response) => response.payment_method));
  }

  updateOrderStatus(companyId: number, statusId: number, input: Partial<AdminOrderStatus>): Observable<AdminOrderStatus> {
    return this.http.patch<{ order_status: AdminOrderStatus }>(`/api/maintainers/companies/${companyId}/order-statuses/${statusId}/`, input, this.options()).pipe(map((response) => response.order_status));
  }

  updateSettings(companyId: number, input: Partial<AdminCompanySettings>): Observable<AdminCompanySettings> {
    return this.http.patch<{ settings: AdminCompanySettings }>(`/api/maintainers/companies/${companyId}/settings/`, input, this.options()).pipe(map((response) => response.settings));
  }

  createCategory(companyId: number, name: string, parent: number | null): Observable<Category> {
    return this.http.post<{ category: Category }>(`/api/maintainers/companies/${companyId}/catalog/categories/`, { name, parent }, this.options()).pipe(map((response) => response.category));
  }

  updateCategory(companyId: number, categoryId: number, input: { name?: string; parent?: number | null; status?: CategoryStatus }): Observable<Category> {
    return this.http.patch<{ category: Category }>(`/api/maintainers/companies/${companyId}/catalog/categories/${categoryId}/`, input, this.options()).pipe(map((response) => response.category));
  }

  createBrand(companyId: number, input: { name: string; is_active?: boolean }): Observable<Brand> {
    return this.http.post<{ brand: Brand }>(`/api/maintainers/companies/${companyId}/catalog/brands/`, input, this.options()).pipe(map((response) => response.brand));
  }

  updateBrand(companyId: number, brandId: number, input: { name?: string; is_active?: boolean }): Observable<Brand> {
    return this.http.patch<{ brand: Brand }>(`/api/maintainers/companies/${companyId}/catalog/brands/${brandId}/`, input, this.options()).pipe(map((response) => response.brand));
  }

  createProduct(companyId: number, input: { name: string; description: string; image_url: string; category: number; brand: number | null; status?: ProductStatus; variant?: { sku: string; gtin: string; base_price: string } }): Observable<Product> {
    return this.http.post<{ product: Product }>(`/api/maintainers/companies/${companyId}/catalog/products/`, input, this.options()).pipe(map((response) => response.product));
  }

  updateProduct(companyId: number, productId: number, input: Record<string, unknown>): Observable<Product> {
    return this.http.patch<{ product: Product }>(`/api/maintainers/companies/${companyId}/catalog/products/${productId}/`, input, this.options()).pipe(map((response) => response.product));
  }

  toggleProduct(companyId: number, productId: number, status: ProductStatus): Observable<Product> {
    return this.http.post<{ product: Product }>(`/api/maintainers/companies/${companyId}/catalog/products/${productId}/toggle/`, { status }, this.options()).pipe(map((response) => response.product));
  }

  createVariant(companyId: number, productId: number, input: Record<string, unknown>): Observable<Product['variants'][number]> {
    return this.http.post<{ variant: Product['variants'][number] }>(`/api/maintainers/companies/${companyId}/catalog/products/${productId}/variants/`, input, this.options()).pipe(map((response) => response.variant));
  }

  updateVariant(companyId: number, productId: number, variantId: number, input: Record<string, unknown>): Observable<Product['variants'][number]> {
    return this.http.patch<{ variant: Product['variants'][number] }>(`/api/maintainers/companies/${companyId}/catalog/products/${productId}/variants/${variantId}/`, input, this.options()).pipe(map((response) => response.variant));
  }

  toggleVariant(companyId: number, productId: number, variantId: number, status: ProductStatus): Observable<Product['variants'][number]> {
    return this.http.post<{ variant: Product['variants'][number] }>(`/api/maintainers/companies/${companyId}/catalog/products/${productId}/variants/${variantId}/toggle/`, { status }, this.options()).pipe(map((response) => response.variant));
  }

  createSupplier(companyId: number, input: Omit<Supplier, 'id'>): Observable<Supplier> {
    return this.http.post<{ supplier: Supplier }>(`/api/maintainers/companies/${companyId}/suppliers/`, input, this.options()).pipe(map((response) => response.supplier));
  }

  updateSupplier(companyId: number, supplierId: number, input: Partial<Supplier>): Observable<Supplier> {
    return this.http.patch<{ supplier: Supplier }>(`/api/maintainers/companies/${companyId}/suppliers/${supplierId}/`, input, this.options()).pipe(map((response) => response.supplier));
  }

  toggleSupplier(companyId: number, supplierId: number, status: Supplier['status']): Observable<Supplier> {
    return this.http.post<{ supplier: Supplier }>(`/api/maintainers/companies/${companyId}/suppliers/${supplierId}/toggle/`, { status }, this.options()).pipe(map((response) => response.supplier));
  }

  createWarehouse(companyId: number, input: { branch: number | null; code: string; name: string; is_active?: boolean }): Observable<Warehouse> {
    return this.http.post<{ warehouse: Warehouse }>(`/api/maintainers/companies/${companyId}/warehouses/`, input, this.options()).pipe(map((response) => response.warehouse));
  }

  updateWarehouse(companyId: number, warehouseId: number, input: { branch: number | null; code: string; name: string; is_active?: boolean }): Observable<Warehouse> {
    return this.http.patch<{ warehouse: Warehouse }>(`/api/maintainers/companies/${companyId}/warehouses/${warehouseId}/`, input, this.options()).pipe(map((response) => response.warehouse));
  }

  lifecyclePreview(companyId: number, resourceType: string, resourceId: number): Observable<LifecyclePreview> {
    return this.http.get<LifecyclePreview>(
      `/api/maintainers/companies/${companyId}/lifecycle/${resourceType}/${resourceId}/`,
      { withCredentials: true },
    );
  }

  lifecycleAction(companyId: number, resourceType: string, resourceId: number, action: 'activate' | 'deactivate'): Observable<unknown> {
    return this.http.post(
      `/api/maintainers/companies/${companyId}/lifecycle/${resourceType}/${resourceId}/`,
      { action },
      this.options(),
    );
  }

  createDeleteChallenge(companyId: number, resourceType: string, resourceId: number, confirmation: string, reason: string): Observable<{ challenge_id: number; token: string; resource: LifecyclePreview }> {
    return this.http.post<{ challenge_id: number; token: string; resource: LifecyclePreview }>(
      `/api/maintainers/companies/${companyId}/lifecycle/${resourceType}/${resourceId}/`,
      { action: 'challenge', confirmation, reason },
      this.options(),
    );
  }

  executeDeleteChallenge(companyId: number, resourceType: string, resourceId: number, challengeId: number, token: string, confirmation: string): Observable<unknown> {
    return this.http.post(
      `/api/maintainers/companies/${companyId}/lifecycle/${resourceType}/${resourceId}/`,
      { action: 'execute', challenge_id: challengeId, token, confirmation },
      this.options(),
    );
  }
}
