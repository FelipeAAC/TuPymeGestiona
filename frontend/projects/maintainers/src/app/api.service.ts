import { HttpClient, HttpHeaders } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { forkJoin, map, Observable, switchMap } from 'rxjs';

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
  OrganizationMembership,
  Product,
  ProductStatus,
  Supplier,
  Warehouse,
} from './models';

@Injectable({ providedIn: 'root' })
export class MaintainersApi {
  private readonly http = inject(HttpClient);

  private csrfHeaders(): HttpHeaders {
    const token =
      document.cookie
        .split('; ')
        .find((entry) => entry.startsWith('csrftoken='))
        ?.split('=')[1] ?? '';

    return token
      ? new HttpHeaders({ 'X-CSRFToken': decodeURIComponent(token) })
      : new HttpHeaders();
  }

  csrf(): Observable<unknown> {
    return this.http.get('/api/auth/csrf/', { withCredentials: true });
  }

  me(): Observable<AuthUser> {
    return this.http
      .get<{ user: AuthUser }>('/api/auth/me/', { withCredentials: true })
      .pipe(map((response) => response.user));
  }

  login(identifier: string, password: string, rememberMe: boolean): Observable<AuthUser> {
    return this.csrf().pipe(
      switchMap(() =>
        this.http.post<{ user: AuthUser }>(
          '/api/auth/login/',
          { identifier, password, remember_me: rememberMe },
          { headers: this.csrfHeaders(), withCredentials: true },
        ),
      ),
      map((response) => response.user),
    );
  }

  logout(): Observable<unknown> {
    return this.http.post(
      '/api/auth/logout/',
      {},
      { headers: this.csrfHeaders(), withCredentials: true },
    );
  }

  context(): Observable<OrganizationMembership[]> {
    return this.http
      .get<{ memberships: OrganizationMembership[] }>('/api/organizations/context/', {
        withCredentials: true,
      })
      .pipe(map((response) => response.memberships));
  }

  overview(companyId: number): Observable<AdministrationOverview> {
    return this.http.get<AdministrationOverview>('/api/administration/overview/', {
      params: { company: companyId.toString() },
      withCredentials: true,
    });
  }

  catalog(companyId: number): Observable<CatalogState> {
    return forkJoin({
      categories: this.http
        .get<{ categories: Category[] }>('/api/catalog/categories/manage/', {
          params: { company: companyId.toString() },
          withCredentials: true,
        })
        .pipe(map((response) => response.categories)),
      products: this.http
        .get<{ products: Product[] }>('/api/catalog/products/', {
          params: { company: companyId.toString() },
          withCredentials: true,
        })
        .pipe(map((response) => response.products)),
      brands: this.http
        .get<{ brands: Brand[] }>('/api/catalog/brands/', {
          params: { company: companyId.toString() },
          withCredentials: true,
        })
        .pipe(map((response) => response.brands)),
    });
  }

  directories(companyId: number): Observable<DirectoryState> {
    return forkJoin({
      suppliers: this.http
        .get<{ suppliers: Supplier[] }>('/api/catalog/suppliers/', {
          params: { company: companyId.toString() },
          withCredentials: true,
        })
        .pipe(map((response) => response.suppliers)),
      warehouses: this.http
        .get<{ warehouses: Warehouse[] }>('/api/organizations/warehouses/', {
          params: { company: companyId.toString() },
          withCredentials: true,
        })
        .pipe(map((response) => response.warehouses)),
    });
  }

  createCompany(input: Partial<AdminCompany>): Observable<AdminCompany> {
    return this.http
      .post<{ company: AdminCompany }>('/api/administration/companies/', input, {
        headers: this.csrfHeaders(),
        withCredentials: true,
      })
      .pipe(map((response) => response.company));
  }

  updateCompany(companyId: number, input: Partial<AdminCompany>): Observable<AdminCompany> {
    return this.http
      .patch<{ company: AdminCompany }>(
        `/api/administration/companies/${companyId}/`,
        input,
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.company));
  }

  createBranch(companyId: number, input: Partial<AdminBranch>): Observable<AdminBranch> {
    return this.http
      .post<{ branch: AdminBranch }>(
        '/api/administration/branches/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.branch));
  }

  updateBranch(companyId: number, branchId: number, input: Partial<AdminBranch>): Observable<AdminBranch> {
    return this.http
      .patch<{ branch: AdminBranch }>(
        `/api/administration/branches/${branchId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.branch));
  }

  createUser(companyId: number, input: Record<string, unknown>): Observable<AdminUser> {
    return this.http
      .post<{ user: AdminUser }>(
        '/api/administration/users/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.user));
  }

  updateUser(companyId: number, membershipId: number, input: Record<string, unknown>): Observable<AdminUser> {
    return this.http
      .patch<{ user: AdminUser }>(
        `/api/administration/users/${membershipId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.user));
  }

  createRole(companyId: number, input: Record<string, unknown>): Observable<AdminRole> {
    return this.http
      .post<{ role: AdminRole }>(
        '/api/administration/roles/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.role));
  }

  updateRole(companyId: number, roleId: number, input: Record<string, unknown>): Observable<AdminRole> {
    return this.http
      .patch<{ role: AdminRole }>(
        `/api/administration/roles/${roleId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.role));
  }

  createPaymentMethod(companyId: number, input: Partial<AdminPaymentMethod>): Observable<AdminPaymentMethod> {
    return this.http
      .post<{ payment_method: AdminPaymentMethod }>(
        '/api/administration/payment-methods/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.payment_method));
  }

  updatePaymentMethod(
    companyId: number,
    methodId: number,
    input: Partial<AdminPaymentMethod>,
  ): Observable<AdminPaymentMethod> {
    return this.http
      .patch<{ payment_method: AdminPaymentMethod }>(
        `/api/administration/payment-methods/${methodId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.payment_method));
  }

  updateOrderStatus(
    companyId: number,
    statusId: number,
    input: Partial<AdminOrderStatus>,
  ): Observable<AdminOrderStatus> {
    return this.http
      .patch<{ order_status: AdminOrderStatus }>(
        `/api/administration/order-statuses/${statusId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.order_status));
  }

  updateSettings(
    companyId: number,
    input: Partial<AdminCompanySettings>,
  ): Observable<AdminCompanySettings> {
    return this.http
      .patch<{ settings: AdminCompanySettings }>(
        '/api/administration/settings/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.settings));
  }

  createCategory(companyId: number, name: string, parent: number | null): Observable<Category> {
    return this.http
      .post<{ category: Omit<Category, 'status'> }>(
        '/api/catalog/categories/',
        { company: companyId, name, parent },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => ({ ...response.category, status: 'ACTIVE' as CategoryStatus })));
  }

  updateCategory(
    companyId: number,
    categoryId: number,
    input: { name?: string; parent?: number | null; status?: CategoryStatus },
  ): Observable<Category> {
    return this.http
      .patch<{ category: Category }>(
        `/api/catalog/categories/${categoryId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.category));
  }

  createBrand(companyId: number, name: string): Observable<Brand> {
    return this.http
      .post<{ brand: Brand }>(
        '/api/catalog/brands/',
        { company: companyId, name },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.brand));
  }

  createProduct(
    companyId: number,
    input: {
      name: string;
      description: string;
      image_url: string;
      category: number;
      brand: number | null;
      variant: { sku: string; gtin: string; base_price: string };
    },
  ): Observable<Product> {
    return this.http
      .post<{ product: Product }>(
        '/api/catalog/products/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.product));
  }

  updateProduct(
    companyId: number,
    productId: number,
    input: {
      name?: string;
      description?: string;
      image_url?: string;
      category?: number;
      brand?: number | null;
      status?: ProductStatus;
    },
  ): Observable<Product> {
    return this.http
      .patch<{ product: Product }>(
        `/api/catalog/products/${productId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.product));
  }

  createSupplier(companyId: number, input: Omit<Supplier, 'id'>): Observable<Supplier> {
    return this.http
      .post<{ supplier: Supplier }>(
        '/api/catalog/suppliers/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.supplier));
  }

  updateSupplier(companyId: number, supplierId: number, input: Omit<Supplier, 'id'>): Observable<Supplier> {
    return this.http
      .patch<{ supplier: Supplier }>(
        `/api/catalog/suppliers/${supplierId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.supplier));
  }

  createWarehouse(
    companyId: number,
    input: { branch: number | null; code: string; name: string },
  ): Observable<Warehouse> {
    return this.http
      .post<{ warehouse: Warehouse }>(
        '/api/organizations/warehouses/',
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.warehouse));
  }

  updateWarehouse(
    companyId: number,
    warehouseId: number,
    input: { branch: number | null; code: string; name: string },
  ): Observable<Warehouse> {
    return this.http
      .patch<{ warehouse: Warehouse }>(
        `/api/organizations/warehouses/${warehouseId}/`,
        { company: companyId, ...input },
        { headers: this.csrfHeaders(), withCredentials: true },
      )
      .pipe(map((response) => response.warehouse));
  }
}
