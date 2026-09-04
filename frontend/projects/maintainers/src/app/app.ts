import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin, Observable } from 'rxjs';

import { MaintainersApi } from './api.service';
import {
  AdministrationOverview,
  AuthUser,
  CatalogState,
  DirectoryState,
  OrganizationMembership,
  Product,
} from './models';

type Section =
  | 'summary'
  | 'organization'
  | 'users'
  | 'roles'
  | 'catalog'
  | 'suppliers'
  | 'warehouses'
  | 'payments'
  | 'settings';

@Component({
  selector: 'maintainers-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class MaintainersApp implements OnInit {
  private readonly api = inject(MaintainersApi);

  readonly user = signal<AuthUser | null>(null);
  readonly memberships = signal<OrganizationMembership[]>([]);
  readonly selectedMembership = signal<OrganizationMembership | null>(null);
  readonly overview = signal<AdministrationOverview | null>(null);
  readonly catalog = signal<CatalogState>({ categories: [], products: [], brands: [] });
  readonly directories = signal<DirectoryState>({ suppliers: [], warehouses: [] });
  readonly section = signal<Section>('summary');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly notice = signal('');

  identifier = '';
  password = '';
  rememberMe = false;

  readonly activeCompanyId = computed(() => this.selectedMembership()?.company.id ?? null);
  readonly activeCompanyName = computed(() => this.selectedMembership()?.company.name ?? '');

  ngOnInit(): void {
    this.restoreSession();
  }

  restoreSession(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.me().subscribe({
      next: (user) => {
        this.user.set(user);
        this.loadMemberships();
      },
      error: () => {
        this.user.set(null);
        this.loading.set(false);
      },
    });
  }

  login(): void {
    if (!this.identifier.trim() || !this.password) {
      this.error.set('Ingresa usuario/correo y contraseña.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.api.login(this.identifier.trim(), this.password, this.rememberMe).subscribe({
      next: (user) => {
        this.user.set(user);
        this.password = '';
        this.loadMemberships();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(this.describeError(error, 'No fue posible iniciar sesión.'));
      },
    });
  }

  logout(): void {
    this.api.logout().subscribe({
      next: () => this.clearSession(),
      error: () => this.clearSession(),
    });
  }

  selectMembership(rawId: string | number): void {
    const id = Number(rawId);
    const membership = this.memberships().find((item) => item.id === id) ?? null;
    this.selectedMembership.set(membership);
    if (membership) {
      this.loadCompanyData(membership.company.id);
    }
  }

  setSection(section: Section): void {
    this.section.set(section);
  }

  refresh(): void {
    const companyId = this.activeCompanyId();
    if (companyId) {
      this.loadCompanyData(companyId);
    }
  }

  createCompany(): void {
    const name = window.prompt('Nombre comercial de la nueva empresa/tienda:')?.trim();
    if (!name) return;
    const rut = window.prompt('RUT:', '')?.trim() ?? '';
    this.runMutation(
      this.api.createCompany({ name, legal_name: name, rut, is_active: true }),
      'Empresa creada.',
      () => this.loadMemberships(),
    );
  }

  editCompany(): void {
    const current = this.overview()?.company;
    if (!current) return;
    const name = window.prompt('Nombre comercial:', current.name)?.trim();
    if (!name) return;
    const contactEmail =
      window.prompt('Correo de contacto:', current.contact_email)?.trim() ?? current.contact_email;
    this.runMutation(
      this.api.updateCompany(current.id, { name, contact_email: contactEmail }),
      'Empresa actualizada.',
      () => this.refresh(),
    );
  }

  createBranch(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const code = window.prompt('Código de sucursal:', 'CASA')?.trim();
    const name = window.prompt('Nombre de sucursal:', 'Casa Matriz')?.trim();
    if (!code || !name) return;
    this.runMutation(
      this.api.createBranch(companyId, { code, name, is_active: true }),
      'Sucursal creada.',
      () => this.refresh(),
    );
  }

  editBranch(branchId: number): void {
    const companyId = this.activeCompanyId();
    const branch = this.overview()?.branches.find((item) => item.id === branchId);
    if (!companyId || !branch) return;
    const name = window.prompt('Nombre de sucursal:', branch.name)?.trim();
    if (!name) return;
    this.runMutation(
      this.api.updateBranch(companyId, branchId, { name }),
      'Sucursal actualizada.',
      () => this.refresh(),
    );
  }

  createUser(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const username = window.prompt('Nombre de usuario:')?.trim();
    const email = window.prompt('Correo:')?.trim();
    const password = window.prompt('Contraseña inicial:') ?? '';
    if (!username || !email || !password) return;
    this.runMutation(
      this.api.createUser(companyId, {
        username,
        email,
        password,
        status: 'ACTIVE',
        role_ids: [],
        branch_ids: [],
      }),
      'Usuario creado.',
      () => this.refresh(),
    );
  }

  toggleUser(membershipId: number): void {
    const companyId = this.activeCompanyId();
    const item = this.overview()?.users.find((user) => user.id === membershipId);
    if (!companyId || !item) return;
    const status = item.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
    this.runMutation(
      this.api.updateUser(companyId, membershipId, { status }),
      'Estado del usuario actualizado.',
      () => this.refresh(),
    );
  }

  createRole(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const name = window.prompt('Nombre del rol:')?.trim();
    if (!name) return;
    const permissionCodes =
      window
        .prompt('Permisos separados por coma (puede quedar vacío):', '')
        ?.split(',')
        .map((item) => item.trim())
        .filter(Boolean) ?? [];
    this.runMutation(
      this.api.createRole(companyId, {
        name,
        status: 'ACTIVE',
        permission_codes: permissionCodes,
      }),
      'Rol creado.',
      () => this.refresh(),
    );
  }

  toggleRole(roleId: number): void {
    const companyId = this.activeCompanyId();
    const role = this.overview()?.roles.find((item) => item.id === roleId);
    if (!companyId || !role) return;
    this.runMutation(
      this.api.updateRole(companyId, roleId, {
        status: role.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE',
      }),
      'Estado del rol actualizado.',
      () => this.refresh(),
    );
  }

  createCategory(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const name = window.prompt('Nombre de categoría:')?.trim();
    if (!name) return;
    this.runMutation(
      this.api.createCategory(companyId, name, null),
      'Categoría creada.',
      () => this.refresh(),
    );
  }

  toggleCategory(categoryId: number): void {
    const companyId = this.activeCompanyId();
    const category = this.catalog().categories.find((item) => item.id === categoryId);
    if (!companyId || !category) return;
    this.runMutation(
      this.api.updateCategory(companyId, categoryId, {
        status: category.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE',
      }),
      'Categoría actualizada.',
      () => this.refresh(),
    );
  }

  createBrand(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const name = window.prompt('Nombre de marca:')?.trim();
    if (!name) return;
    this.runMutation(this.api.createBrand(companyId, name), 'Marca creada.', () => this.refresh());
  }

  createProduct(): void {
    const companyId = this.activeCompanyId();
    const category = this.catalog().categories.find((item) => item.status === 'ACTIVE');
    if (!companyId || !category) {
      this.error.set('Necesitas al menos una categoría activa para crear productos.');
      return;
    }
    const name = window.prompt('Nombre del producto:')?.trim();
    const sku = window.prompt('SKU de variante:', '')?.trim();
    const basePrice = window.prompt('Precio base:', '0')?.trim();
    if (!name || !sku || !basePrice) return;
    this.runMutation(
      this.api.createProduct(companyId, {
        name,
        description: '',
        image_url: '',
        category: category.id,
        brand: null,
        variant: { sku, gtin: '', base_price: basePrice },
      }),
      'Producto creado.',
      () => this.refresh(),
    );
  }

  toggleProduct(product: Product): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    this.runMutation(
      this.api.updateProduct(companyId, product.id, {
        status: product.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE',
      }),
      'Producto actualizado.',
      () => this.refresh(),
    );
  }

  createSupplier(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const name = window.prompt('Nombre del proveedor:')?.trim();
    if (!name) return;
    this.runMutation(
      this.api.createSupplier(companyId, {
        name,
        contact_name: '',
        email: '',
        phone: '',
        status: 'ACTIVE',
      }),
      'Proveedor creado.',
      () => this.refresh(),
    );
  }

  toggleSupplier(supplierId: number): void {
    const companyId = this.activeCompanyId();
    const supplier = this.directories().suppliers.find((item) => item.id === supplierId);
    if (!companyId || !supplier) return;
    this.runMutation(
      this.api.updateSupplier(companyId, supplierId, {
        name: supplier.name,
        contact_name: supplier.contact_name,
        email: supplier.email,
        phone: supplier.phone,
        status: supplier.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE',
      }),
      'Proveedor actualizado.',
      () => this.refresh(),
    );
  }

  createWarehouse(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const code = window.prompt('Código de bodega:')?.trim();
    const name = window.prompt('Nombre de bodega:')?.trim();
    if (!code || !name) return;
    this.runMutation(
      this.api.createWarehouse(companyId, { branch: null, code, name }),
      'Bodega creada.',
      () => this.refresh(),
    );
  }

  editWarehouse(warehouseId: number): void {
    const companyId = this.activeCompanyId();
    const warehouse = this.directories().warehouses.find((item) => item.id === warehouseId);
    if (!companyId || !warehouse) return;
    const name = window.prompt('Nombre de bodega:', warehouse.name)?.trim();
    if (!name) return;
    this.runMutation(
      this.api.updateWarehouse(companyId, warehouseId, {
        branch: warehouse.branch,
        code: warehouse.code,
        name,
      }),
      'Bodega actualizada.',
      () => this.refresh(),
    );
  }

  createPaymentMethod(): void {
    const companyId = this.activeCompanyId();
    if (!companyId) return;
    const code = window.prompt('Código del método:', 'TRANSFER')?.trim();
    const name = window.prompt('Nombre visible:', 'Transferencia')?.trim();
    if (!code || !name) return;
    this.runMutation(
      this.api.createPaymentMethod(companyId, {
        code,
        name,
        kind: 'TRANSFER',
        is_active: true,
        sort_order: 0,
      }),
      'Método de pago creado.',
      () => this.refresh(),
    );
  }

  togglePaymentMethod(methodId: number): void {
    const companyId = this.activeCompanyId();
    const method = this.overview()?.payment_methods.find((item) => item.id === methodId);
    if (!companyId || !method) return;
    this.runMutation(
      this.api.updatePaymentMethod(companyId, methodId, { is_active: !method.is_active }),
      'Método de pago actualizado.',
      () => this.refresh(),
    );
  }

  toggleOrderStatus(statusId: number): void {
    const companyId = this.activeCompanyId();
    const status = this.overview()?.order_statuses.find((item) => item.id === statusId);
    if (!companyId || !status || status.is_system) return;
    this.runMutation(
      this.api.updateOrderStatus(companyId, statusId, { is_active: !status.is_active }),
      'Estado de pedido actualizado.',
      () => this.refresh(),
    );
  }

  editSettings(): void {
    const companyId = this.activeCompanyId();
    const settings = this.overview()?.settings;
    if (!companyId || !settings) return;
    const sender =
      window.prompt('Correo remitente:', settings.notification_sender_email)?.trim() ??
      settings.notification_sender_email;
    const timezone = window.prompt('Zona horaria:', settings.timezone)?.trim() ?? settings.timezone;
    this.runMutation(
      this.api.updateSettings(companyId, {
        notification_sender_email: sender,
        timezone,
      }),
      'Parámetros actualizados.',
      () => this.refresh(),
    );
  }

  private loadMemberships(): void {
    this.loading.set(true);
    this.api.context().subscribe({
      next: (memberships) => {
        this.memberships.set(memberships);
        const active =
          memberships.find((item) => item.status === 'ACTIVE') ?? memberships[0] ?? null;
        this.selectedMembership.set(active);
        if (active) {
          this.loadCompanyData(active.company.id);
        } else {
          this.loading.set(false);
          this.error.set('El usuario no tiene empresas disponibles.');
        }
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(this.describeError(error, 'No fue posible cargar las empresas.'));
      },
    });
  }

  private loadCompanyData(companyId: number): void {
    this.loading.set(true);
    this.error.set('');
    this.notice.set('');
    forkJoin({
      overview: this.api.overview(companyId),
      catalog: this.api.catalog(companyId),
      directories: this.api.directories(companyId),
    }).subscribe({
      next: ({ overview, catalog, directories }) => {
        this.overview.set(overview);
        this.catalog.set(catalog);
        this.directories.set(directories);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.overview.set(null);
        this.loading.set(false);
        this.error.set(
          this.describeError(
            error,
            'No fue posible cargar los mantenedores. Verifica permisos de administración.',
          ),
        );
      },
    });
  }

  private runMutation<T>(observable: Observable<T>, message: string, next: () => void): void {
    this.loading.set(true);
    this.error.set('');
    this.notice.set('');
    observable.subscribe({
      next: () => {
        this.notice.set(message);
        next();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(this.describeError(error, 'La operación no pudo completarse.'));
      },
    });
  }

  private clearSession(): void {
    this.user.set(null);
    this.memberships.set([]);
    this.selectedMembership.set(null);
    this.overview.set(null);
    this.catalog.set({ categories: [], products: [], brands: [] });
    this.directories.set({ suppliers: [], warehouses: [] });
    this.section.set('summary');
    this.loading.set(false);
    this.error.set('');
    this.notice.set('');
  }

  private describeError(error: unknown, fallback: string): string {
    if (typeof error === 'object' && error !== null && 'error' in error) {
      const body = (error as { error?: { detail?: unknown; message?: unknown } }).error;
      if (typeof body?.detail === 'string') return body.detail;
      if (typeof body?.message === 'string') return body.message;
    }
    return fallback;
  }
}
