import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin, Observable, switchMap } from 'rxjs';

import { MaintainersApi } from './api.service';
import { FormDialogComponent, FormDialogField } from './form-dialog.component';
import {
  AdminCompany,
  AdminCompanySettings,
  AdministrationOverview,
  AuthUser,
  CatalogState,
  DirectoryState,
  LifecyclePreview,
  MaintainerAuditEvent,
  MaintainerContext,
  Product,
} from './models';

type Section = 'summary' | 'organization' | 'users' | 'roles' | 'catalog' | 'suppliers' | 'warehouses' | 'payments' | 'settings' | 'audit';
type DialogState = { title: string; fields: FormDialogField[]; initialValue: Record<string, unknown>; save: (value: Record<string, unknown>) => void; error?: string };
type DangerState = {
  companyId: number;
  resourceType: string;
  resourceId: number;
  preview: LifecyclePreview;
  confirmationInput: string;
  reason: string;
  acknowledged: boolean;
  progress: number;
  error: string;
};

@Component({
  selector: 'maintainers-root',
  standalone: true,
  imports: [CommonModule, FormsModule, FormDialogComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class MaintainersApp implements OnInit {
  private readonly api = inject(MaintainersApi);

  readonly user = signal<AuthUser | null>(null);
  readonly context = signal<MaintainerContext | null>(null);
  readonly selectedCompanyId = signal<number | null>(null);
  readonly overview = signal<AdministrationOverview | null>(null);
  readonly catalog = signal<CatalogState>({ categories: [], products: [], brands: [] });
  readonly directories = signal<DirectoryState>({ suppliers: [], warehouses: [] });
  readonly auditEvents = signal<MaintainerAuditEvent[]>([]);
  readonly auditTotal = signal(0);
  readonly auditHasNext = signal(false);
  readonly auditPage = signal(1);
  readonly auditError = signal('');
  readonly section = signal<Section>('summary');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly dialog = signal<DialogState | null>(null);
  readonly danger = signal<DangerState | null>(null);
  private dangerTimer: number | null = null;

  identifier = '';
  password = '';
  rememberMe = false;
  auditActorFilter = '';
  auditEventFilter = '';
  auditResourceFilter = '';
  auditCompanyFilter = '';
  auditFromFilter = '';
  auditToFilter = '';

  readonly companies = computed(() => this.context()?.companies ?? []);
  readonly selectedCompany = computed(() => this.companies().find((company) => company.id === this.selectedCompanyId()) ?? null);
  readonly activeCompanyId = computed(() => this.selectedCompanyId());
  readonly activeCompanyName = computed(() => this.selectedCompany()?.name ?? '');

  ngOnInit(): void { this.restoreSession(); }

  restoreSession(): void {
    this.beginLoad();
    this.api.me().subscribe({
      next: (user) => {
        if (!this.isPlatformAdmin(user)) { this.rejectNonPlatform(); return; }
        this.user.set(user);
        this.loadContext();
      },
      error: () => { this.user.set(null); this.loading.set(false); },
    });
  }

  login(): void {
    this.clearStatus();
    if (!this.identifier.trim() || !this.password) { this.error.set('Ingresa usuario/correo y contraseña.'); return; }
    this.loading.set(true);
    this.api.login(this.identifier.trim(), this.password, this.rememberMe).subscribe({
      next: (user) => {
        this.password = '';
        if (!this.isPlatformAdmin(user)) { this.rejectNonPlatform(); return; }
        this.user.set(user);
        this.loadContext();
      },
      error: (error: unknown) => { this.loading.set(false); this.error.set(this.describeError(error, 'No fue posible iniciar sesión.')); },
    });
  }

  logout(): void { this.api.logout().subscribe({ next: () => this.clearSession(), error: () => this.clearSession() }); }
  isPlatformAdmin(user: AuthUser): boolean { return user.access_modes?.includes('PLATFORM_ADMIN') ?? false; }

  selectCompany(rawId: string | number): void {
    const id = Number(rawId);
    if (!Number.isFinite(id)) return;
    this.selectedCompanyId.set(id);
    this.loadCompanyData(id);
  }

  setSection(section: Section): void { this.clearStatus(); this.section.set(section); if (section === 'audit') this.loadAudit(); }
  refresh(): void { const id = this.activeCompanyId(); if (id) this.loadCompanyData(id); this.loadAudit(); }
  isDestructiveAdmin(): boolean { return this.user()?.destructive_admin === true; }

  auditImpact(event: MaintainerAuditEvent): string {
    const impact = event.metadata?.['impact'];
    if (!Array.isArray(impact)) return '—';
    const labels: Record<string, string> = {
      'payment methods': 'métodos de pago',
      'company settings': 'configuración general',
      'company settingss': 'configuración general',
      'order status configurations': 'estados de pedido',
      'administration events': 'eventos administrativos',
    };
    return impact.map((item) => {
      if (!item || typeof item !== 'object') return '';
      const row = item as { count?: unknown; label?: unknown };
      const rawLabel = String(row.label ?? 'relación');
      return `${String(row.count ?? 0)} · ${labels[rawLabel.toLowerCase()] ?? rawLabel}`;
    }).filter(Boolean).join(' · ') || 'Sin relaciones';
  }

  auditDetails(event: MaintainerAuditEvent): string {
    const groups = event.metadata?.['deleted_related'];
    if (!Array.isArray(groups)) return 'Sin detalle adicional';
    const labels = groups.map((group) => {
      if (!group || typeof group !== 'object') return '';
      const row = group as { label?: unknown; items?: unknown[]; truncated?: unknown };
      const count = Array.isArray(row.items) ? row.items.length : 0;
      return `${String(row.label ?? 'Relación')}: ${count}${row.truncated ? '+' : ''}`;
    }).filter(Boolean);
    return labels.join(' · ') || 'Sin registros relacionados';
  }

  applyAuditFilters(): void { this.auditPage.set(1); this.loadAudit(); }
  changeAuditPage(delta: number): void { this.auditPage.update(page => Math.max(1, page + delta)); this.loadAudit(); }
  clearAuditFilters(): void {
    this.auditPage.set(1);
    this.auditActorFilter = '';
    this.auditEventFilter = '';
    this.auditResourceFilter = '';
    this.auditCompanyFilter = '';
    this.auditFromFilter = '';
    this.auditToFilter = '';
    this.loadAudit();
  }

  toggleResource(resourceType: string, resourceId: number, currentlyActive: boolean, explicitCompanyId?: number): void {
    const companyId = explicitCompanyId ?? this.activeCompanyId();
    if (!companyId) return;
    this.runMutation(
      this.api.lifecycleAction(companyId, resourceType, resourceId, currentlyActive ? 'deactivate' : 'activate'),
      currentlyActive ? 'Recurso desactivado.' : 'Recurso reactivado.',
      () => resourceType === 'company' ? this.loadContext() : this.refresh(),
    );
  }

  openDanger(resourceType: string, resourceId: number, explicitCompanyId?: number): void {
    const companyId = explicitCompanyId ?? this.activeCompanyId();
    if (!companyId || !this.isDestructiveAdmin()) {
      this.error.set('La eliminación permanente está reservada a la cuenta autorizada.');
      return;
    }
    this.loading.set(true);
    this.clearStatus();
    this.api.lifecyclePreview(companyId, resourceType, resourceId).subscribe({
      next: (preview) => {
        this.loading.set(false);
        this.danger.set({
          companyId,
          resourceType,
          resourceId,
          preview,
          confirmationInput: '',
          reason: '',
          acknowledged: false,
          progress: 0,
          error: '',
        });
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(this.describeError(error, 'No fue posible preparar la eliminación.'));
      },
    });
  }

  closeDanger(): void {
    this.stopDangerHold();
    this.danger.set(null);
  }

  dangerReady(): boolean {
    const danger = this.danger();
    return Boolean(
      danger?.preview.can_hard_delete
      && danger.confirmationInput === danger.preview.confirmation_phrase
      && danger.reason.trim().length > 0
      && danger.acknowledged,
    );
  }

  updateDangerInput(value: string): void {
    const danger = this.danger();
    if (danger) this.danger.set({ ...danger, confirmationInput: value, error: '' });
  }

  updateDangerAcknowledged(value: boolean): void {
    const danger = this.danger();
    if (danger) this.danger.set({ ...danger, acknowledged: value, error: '' });
  }

  updateDangerReason(value: string): void {
    const danger = this.danger();
    if (danger) this.danger.set({ ...danger, reason: value, error: '' });
  }

  startDangerHold(): void {
    if (!this.dangerReady() || this.dangerTimer !== null) return;
    this.dangerTimer = window.setInterval(() => {
      const danger = this.danger();
      if (!danger || !this.dangerReady()) {
        this.stopDangerHold();
        return;
      }
      const progress = Math.min(100, danger.progress + 4);
      this.danger.set({ ...danger, progress });
      if (progress >= 100) {
        this.stopDangerHold(false);
        this.executeDanger(danger);
      }
    }, 200);
  }

  stopDangerHold(reset = true): void {
    if (this.dangerTimer !== null) {
      window.clearInterval(this.dangerTimer);
      this.dangerTimer = null;
    }
    const danger = this.danger();
    if (reset && danger && danger.progress < 100) this.danger.set({ ...danger, progress: 0 });
  }

  createCompany(): void {
    this.openDialog('Nueva empresa', [
      this.text('name', 'Nombre comercial', true), this.text('legal_name', 'Razón social', true), this.text('rut', 'RUT'),
      this.text('business_activity', 'Giro'), this.email('contact_email', 'Correo de contacto'), this.text('phone', 'Teléfono'),
      this.text('address', 'Dirección'), this.text('commune', 'Comuna'), this.text('city', 'Ciudad'),
    ], {}, (value) => this.runMutation(this.api.createCompany(value as Partial<AdminCompany>), 'Empresa creada.', () => { this.closeDialog(); this.loadContext(); }));
  }

  editCompany(): void {
    const current = this.overview()?.company; if (!current) return;
    this.openDialog('Editar empresa', [this.text('name', 'Nombre comercial', true), this.text('legal_name', 'Razón social'), this.text('rut', 'RUT'), this.text('business_activity', 'Giro'), this.email('contact_email', 'Correo de contacto'), this.text('phone', 'Teléfono'), this.text('address', 'Dirección'), this.text('commune', 'Comuna'), this.text('city', 'Ciudad'), this.checkbox('is_active', 'Empresa activa')], { ...current }, (value) => this.runMutation(this.api.updateCompany(current.id, value as Partial<AdminCompany>), 'Empresa actualizada.', () => { this.closeDialog(); this.refresh(); }));
  }

  createBranch(): void {
    const id = this.activeCompanyId(); if (!id) return;
    this.openDialog('Nueva sucursal', [this.text('code', 'Código', true), this.text('name', 'Nombre', true), this.text('address', 'Dirección'), this.text('commune', 'Comuna'), this.text('city', 'Ciudad'), this.text('phone', 'Teléfono'), this.checkbox('is_active', 'Sucursal activa')], { is_active: true }, (value) => this.runMutation(this.api.createBranch(id, value), 'Sucursal creada.', () => { this.closeDialog(); this.refresh(); }));
  }

  editBranch(branchId: number): void {
    const id = this.activeCompanyId(); const branch = this.overview()?.branches.find((item) => item.id === branchId); if (!id || !branch) return;
    this.openDialog('Editar sucursal', [this.text('code', 'Código', true), this.text('name', 'Nombre', true), this.text('address', 'Dirección'), this.text('commune', 'Comuna'), this.text('city', 'Ciudad'), this.text('phone', 'Teléfono'), this.checkbox('is_active', 'Sucursal activa')], { ...branch }, (value) => this.runMutation(this.api.updateBranch(id, branchId, value as any), 'Sucursal actualizada.', () => { this.closeDialog(); this.refresh(); }));
  }

  createUser(): void {
    const id = this.activeCompanyId(); const data = this.overview(); if (!id || !data) return;
    this.openDialog('Nuevo usuario', [this.text('username', 'Usuario', true), this.email('email', 'Correo', true), this.text('first_name', 'Nombre'), this.text('last_name', 'Apellido'), { key: 'password', label: 'Contraseña inicial', type: 'password', required: true }, this.select('status', 'Estado', ['INVITED', 'ACTIVE', 'SUSPENDED']), this.multi('role_ids', 'Roles', this.roleOptions(data.roles, data.permissions), 'Puedes asignar uno o varios roles. Las sucursales seleccionadas limitan los permisos por sucursal.'), this.multi('branch_ids', 'Sucursales', data.branches.map((branch) => ({ value: branch.id, label: `${branch.code} · ${branch.name}` })), 'Obligatorio cuando alguno de los roles tiene permisos por sucursal.')], { status: 'ACTIVE', role_ids: [], branch_ids: [] }, (value) => this.runMutation(this.api.createUser(id, value), 'Usuario creado.', () => { this.closeDialog(); this.refresh(); }));
  }

  editUser(itemId: number): void {
    const id = this.activeCompanyId(); const data = this.overview(); const item = data?.users.find((user) => user.id === itemId); if (!id || !data || !item) return;
    this.openDialog('Editar usuario', [this.text('first_name', 'Nombre'), this.text('last_name', 'Apellido'), this.select('status', 'Estado', ['INVITED', 'ACTIVE', 'SUSPENDED', 'LEFT']), this.multi('role_ids', 'Roles', this.roleOptions(data.roles, data.permissions), 'Puedes asignar uno o varios roles. Las sucursales seleccionadas limitan los permisos por sucursal.'), this.multi('branch_ids', 'Sucursales', data.branches.map((branch) => ({ value: branch.id, label: `${branch.code} · ${branch.name}` })), 'Obligatorio cuando alguno de los roles tiene permisos por sucursal.')], { ...item }, (value) => this.runMutation(this.api.updateUser(id, itemId, value), 'Usuario actualizado.', () => { this.closeDialog(); this.refresh(); }));
  }

  toggleUser(id: number): void { const item = this.overview()?.users.find((user) => user.id === id); const companyId = this.activeCompanyId(); if (!item || !companyId) return; this.runMutation(this.api.updateUser(companyId, id, { status: item.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE' }), 'Estado del usuario actualizado.', () => this.refresh()); }
  revokeUserAccess(id: number): void {
    const companyId = this.activeCompanyId();
    const item = this.overview()?.users.find((user) => user.id === id);
    if (!companyId || !item) return;
    const phrase = `DESVINCULAR ${item.email}`;
    this.openDialog('Quitar acceso a la empresa', [this.text('confirmation', `Escribe ${phrase}`, true)], {}, (value) => {
      if (String(value['confirmation'] ?? '').trim() !== phrase) {
        const current = this.dialog();
        if (current) this.dialog.set({ ...current, error: `Debes escribir exactamente: ${phrase}` });
        return;
      }
      this.runMutation(this.api.revokeUserAccess(companyId, id), 'Acceso de empresa quitado. La cuenta global se conserva.', () => { this.closeDialog(); this.refresh(); });
    });
  }

  createRole(): void {
    const id = this.activeCompanyId(); const data = this.overview(); if (!id || !data) return;
    this.openDialog('Nuevo rol', [this.text('name', 'Nombre del rol', true), this.select('status', 'Estado', ['ACTIVE', 'INACTIVE']), this.multi('permission_codes', 'Permisos', data.permissions.map((permission) => ({ value: permission.code, label: `${permission.code} · ${permission.scope_behavior}` })))], { status: 'ACTIVE', permission_codes: [] }, (value) => this.runMutation(this.api.createRole(id, value), 'Rol creado.', () => { this.closeDialog(); this.refresh(); }));
  }

  editRole(roleId: number): void { const id = this.activeCompanyId(); const role = this.overview()?.roles.find((item) => item.id === roleId); if (!id || !role) return; this.openDialog('Editar rol', [this.text('name', 'Nombre', true), this.select('status', 'Estado', ['ACTIVE', 'INACTIVE']), this.multi('permission_codes', 'Permisos', this.overview()?.permissions.map((permission) => ({ value: permission.code, label: permission.code })) ?? [])], { ...role }, (value) => this.runMutation(this.api.updateRole(id, roleId, value), 'Rol actualizado.', () => { this.closeDialog(); this.refresh(); })); }
  toggleRole(roleId: number): void { const id = this.activeCompanyId(); const role = this.overview()?.roles.find((item) => item.id === roleId); if (!id || !role) return; this.runMutation(this.api.updateRole(id, roleId, { status: role.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' }), 'Estado del rol actualizado.', () => this.refresh()); }

  createCategory(): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog('Nueva categoría', [this.text('name', 'Nombre', true), this.select('parent', 'Categoría padre', [{ value: '', label: 'Sin categoría padre' }, ...(this.catalog().categories.map((item) => ({ value: item.id, label: item.name })))] )], { parent: '' }, (value) => this.runMutation(this.api.createCategory(id, String(value['name']), value['parent'] ? Number(value['parent']) : null), 'Categoría creada.', () => { this.closeDialog(); this.refresh(); })); }
  editCategory(categoryId: number): void { const id = this.activeCompanyId(); const category = this.catalog().categories.find((item) => item.id === categoryId); if (!id || !category) return; this.openDialog('Editar categoría', [this.text('name', 'Nombre', true), this.select('status', 'Estado', ['ACTIVE', 'INACTIVE'])], { ...category }, (value) => this.runMutation(this.api.updateCategory(id, categoryId, value as { name?: string; status?: 'ACTIVE' | 'INACTIVE' }), 'Categoría actualizada.', () => { this.closeDialog(); this.refresh(); })); }
  toggleCategory(categoryId: number): void { const id = this.activeCompanyId(); const category = this.catalog().categories.find((item) => item.id === categoryId); if (!id || !category) return; this.runMutation(this.api.updateCategory(id, categoryId, { status: category.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' }), 'Categoría actualizada.', () => this.refresh()); }
  createBrand(): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog('Nueva marca', [this.text('name', 'Nombre', true), this.checkbox('is_active', 'Marca activa')], { is_active: true }, (value) => this.runMutation(this.api.createBrand(id, { name: String(value['name']), is_active: Boolean(value['is_active']) }), 'Marca creada.', () => { this.closeDialog(); this.refresh(); })); }
  editBrand(brandId: number): void { const id = this.activeCompanyId(); const brand = this.catalog().brands.find((item) => item.id === brandId); if (!id || !brand) return; this.openDialog('Editar marca', [this.text('name', 'Nombre', true), this.checkbox('is_active', 'Marca activa')], { ...brand }, (value) => this.runMutation(this.api.updateBrand(id, brandId, { name: String(value['name']), is_active: Boolean(value['is_active']) }), 'Marca actualizada.', () => { this.closeDialog(); this.refresh(); })); }

  createProduct(): void {
    const id = this.activeCompanyId(); const categories = this.catalog().categories.filter((item) => item.status === 'ACTIVE'); if (!id || !categories.length) { this.error.set('Necesitas al menos una categoría activa para crear productos.'); return; }
    this.openDialog('Nuevo producto', [this.text('name', 'Nombre', true), this.text('description', 'Descripción'), this.text('image_url', 'URL de imagen'), this.select('category', 'Categoría', categories.map((item) => ({ value: item.id, label: item.name }))), this.select('brand', 'Marca', [{ value: '', label: 'Sin marca' }, ...this.catalog().brands.map((brand) => ({ value: brand.id, label: brand.name }))]), this.text('sku', 'SKU inicial', true), this.text('gtin', 'GTIN'), this.number('base_price', 'Precio base', 0)], { category: categories[0].id, brand: '', base_price: '0' }, (value) => this.runMutation(this.api.createProduct(id, { name: String(value['name']), description: String(value['description'] ?? ''), image_url: String(value['image_url'] ?? ''), category: Number(value['category']), brand: value['brand'] ? Number(value['brand']) : null, variant: { sku: String(value['sku']), gtin: String(value['gtin'] ?? ''), base_price: String(value['base_price']) } }), 'Producto creado.', () => { this.closeDialog(); this.refresh(); }));
  }

  editProduct(product: Product): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog('Editar producto', [this.text('name', 'Nombre', true), this.text('description', 'Descripción'), this.text('image_url', 'URL de imagen'), this.select('category', 'Categoría', this.catalog().categories.map((item) => ({ value: item.id, label: item.name }))), this.select('brand', 'Marca', [{ value: '', label: 'Sin marca' }, ...this.catalog().brands.map((brand) => ({ value: brand.id, label: brand.name }))]), this.select('status', 'Estado', ['DRAFT', 'ACTIVE', 'INACTIVE'])], { ...product, category: product.category.id, brand: product.brand?.id ?? '' }, (value) => this.runMutation(this.api.updateProduct(id, product.id, { name: value['name'], description: value['description'], image_url: value['image_url'], category: Number(value['category']), brand: value['brand'] ? Number(value['brand']) : null, status: value['status'] }), 'Producto actualizado.', () => { this.closeDialog(); this.refresh(); })); }
  toggleProduct(product: Product): void { const id = this.activeCompanyId(); if (!id) return; this.runMutation(this.api.toggleProduct(id, product.id, product.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'), 'Estado del producto actualizado.', () => this.refresh()); }

  createVariant(product: Product): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog(`Nueva variante · ${product.name}`, [this.text('sku', 'SKU', true), this.text('gtin', 'GTIN'), this.number('base_price', 'Precio base', 0), this.select('status', 'Estado', ['DRAFT', 'ACTIVE', 'INACTIVE'])], { status: 'ACTIVE', base_price: '0' }, (value) => this.runMutation(this.api.createVariant(id, product.id, { sku: value['sku'], gtin: value['gtin'], base_price: String(value['base_price']), status: value['status'] }), 'Variante creada.', () => { this.closeDialog(); this.refresh(); })); }
  editVariant(product: Product, variant: Product['variants'][number]): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog(`Editar variante · ${product.name}`, [this.text('sku', 'SKU', true), this.text('gtin', 'GTIN'), this.number('base_price', 'Precio base', 0), this.select('status', 'Estado', ['DRAFT', 'ACTIVE', 'INACTIVE'])], variant, (value) => this.runMutation(this.api.updateVariant(id, product.id, variant.id, { sku: value['sku'], gtin: value['gtin'], base_price: String(value['base_price']), status: value['status'] }), 'Variante actualizada.', () => { this.closeDialog(); this.refresh(); })); }
  toggleVariant(product: Product, variant: Product['variants'][number]): void { const id = this.activeCompanyId(); if (!id) return; this.runMutation(this.api.toggleVariant(id, product.id, variant.id, variant.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'), 'Estado de la variante actualizado.', () => this.refresh()); }

  createSupplier(): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog('Nuevo proveedor', [this.text('name', 'Nombre', true), this.text('contact_name', 'Contacto'), this.email('email', 'Correo'), this.text('phone', 'Teléfono'), this.select('status', 'Estado', ['ACTIVE', 'INACTIVE'])], { status: 'ACTIVE' }, (value) => this.runMutation(this.api.createSupplier(id, value as any), 'Proveedor creado.', () => { this.closeDialog(); this.refresh(); })); }
  editSupplier(id: number): void { const companyId = this.activeCompanyId(); const supplier = this.directories().suppliers.find((item) => item.id === id); if (!companyId || !supplier) return; this.openDialog('Editar proveedor', [this.text('name', 'Nombre', true), this.text('contact_name', 'Contacto'), this.email('email', 'Correo'), this.text('phone', 'Teléfono'), this.select('status', 'Estado', ['ACTIVE', 'INACTIVE'])], { ...supplier }, (value) => this.runMutation(this.api.updateSupplier(companyId, id, value as any), 'Proveedor actualizado.', () => { this.closeDialog(); this.refresh(); })); }
  toggleSupplier(id: number): void { const companyId = this.activeCompanyId(); const supplier = this.directories().suppliers.find((item) => item.id === id); if (!companyId || !supplier) return; this.runMutation(this.api.toggleSupplier(companyId, id, supplier.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'), 'Estado del proveedor actualizado.', () => this.refresh()); }

  createWarehouse(): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog('Nueva bodega', [this.text('code', 'Código', true), this.text('name', 'Nombre', true), this.select('branch', 'Sucursal', [{ value: '', label: 'General' }, ...(this.overview()?.branches.map((branch) => ({ value: branch.id, label: `${branch.code} · ${branch.name}` })) ?? [])]), this.checkbox('is_active', 'Bodega activa')], { branch: '', is_active: true }, (value) => this.runMutation(this.api.createWarehouse(id, { code: String(value['code']), name: String(value['name']), branch: value['branch'] ? Number(value['branch']) : null, is_active: Boolean(value['is_active']) }), 'Bodega creada.', () => { this.closeDialog(); this.refresh(); })); }
  editWarehouse(warehouseId: number): void { const id = this.activeCompanyId(); const warehouse = this.directories().warehouses.find((item) => item.id === warehouseId); if (!id || !warehouse) return; this.openDialog('Editar bodega', [this.text('code', 'Código', true), this.text('name', 'Nombre', true), this.select('branch', 'Sucursal', [{ value: '', label: 'General' }, ...(this.overview()?.branches.map((branch) => ({ value: branch.id, label: `${branch.code} · ${branch.name}` })) ?? [])]), this.checkbox('is_active', 'Bodega activa')], { ...warehouse, branch: warehouse.branch ?? '', is_active: warehouse.is_active }, (value) => this.runMutation(this.api.updateWarehouse(id, warehouseId, { code: String(value['code']), name: String(value['name']), branch: value['branch'] ? Number(value['branch']) : null, is_active: Boolean(value['is_active']) }), 'Bodega actualizada.', () => { this.closeDialog(); this.refresh(); })); }

  createPaymentMethod(): void { const id = this.activeCompanyId(); if (!id) return; this.openDialog('Nuevo método de pago', [this.text('code', 'Código', true), this.text('name', 'Nombre visible', true), this.select('kind', 'Tipo', ['CASH', 'TRANSFER', 'ONLINE', 'OTHER']), this.number('sort_order', 'Orden', 0), this.checkbox('is_active', 'Activo')], { kind: 'TRANSFER', sort_order: 0, is_active: true }, (value) => this.runMutation(this.api.createPaymentMethod(id, { code: String(value['code']), name: String(value['name']), kind: value['kind'] as any, sort_order: Number(value['sort_order']), is_active: Boolean(value['is_active']) }), 'Método de pago creado.', () => { this.closeDialog(); this.refresh(); })); }
  togglePaymentMethod(methodId: number): void { const id = this.activeCompanyId(); const method = this.overview()?.payment_methods.find((item) => item.id === methodId); if (!id || !method) return; this.runMutation(this.api.updatePaymentMethod(id, methodId, { is_active: !method.is_active }), 'Método de pago actualizado.', () => this.refresh()); }
  toggleOrderStatus(statusId: number): void { const id = this.activeCompanyId(); const status = this.overview()?.order_statuses.find((item) => item.id === statusId); if (!id || !status || status.is_system) return; this.runMutation(this.api.updateOrderStatus(id, statusId, { is_active: !status.is_active }), 'Estado de pedido actualizado.', () => this.refresh()); }
  editSettings(): void { const id = this.activeCompanyId(); const settings = this.overview()?.settings; if (!id || !settings) return; this.openDialog('Parámetros generales', [this.number('vat_rate', 'IVA', 0), this.text('currency', 'Moneda', true), this.text('timezone', 'Zona horaria', true), this.text('payment_provider', 'Proveedor de pago'), this.checkbox('payment_sandbox_enabled', 'Sandbox activo'), this.email('notification_sender_email', 'Correo remitente')], { ...settings }, (value) => this.runMutation(this.api.updateSettings(id, { ...value, vat_rate: String(value['vat_rate']) } as Partial<AdminCompanySettings>), 'Parámetros actualizados.', () => { this.closeDialog(); this.refresh(); })); }

  submitDialog(value: Record<string, unknown>): void { this.dialog()?.save(value); }
  closeDialog(): void { this.dialog.set(null); }

  private openDialog(title: string, fields: FormDialogField[], initialValue: Record<string, unknown>, save: (value: Record<string, unknown>) => void): void { this.clearStatus(); this.dialog.set({ title, fields, initialValue, save, error: '' }); }
  private text(key: string, label: string, required = false): FormDialogField { return { key, label, type: 'text', required }; }
  private email(key: string, label: string, required = false): FormDialogField { return { key, label, type: 'email', required }; }
  private number(key: string, label: string, min?: number): FormDialogField { return { key, label, type: 'number', min }; }
  private checkbox(key: string, label: string): FormDialogField { return { key, label, type: 'checkbox' }; }
  private select(key: string, label: string, values: string[] | { value: string | number; label: string }[]): FormDialogField { return { key, label, type: 'select', options: values.map((value) => typeof value === 'string' ? { value, label: value } : value) }; }
  private multi(key: string, label: string, options: { value: string | number; label: string }[], hint = ''): FormDialogField { return { key, label, type: 'multi-select', options, hint }; }
  private roleOptions(roles: AdministrationOverview['roles'], permissions: AdministrationOverview['permissions']): { value: number; label: string }[] { return roles.map((role) => ({ value: role.id, label: `${role.name} · ${this.roleScopeLabel(role, permissions)}` })); }
  private roleScopeLabel(role: AdministrationOverview['roles'][number], permissions: AdministrationOverview['permissions']): string {
    const scopes = new Set(role.permission_codes.map((code) => permissions.find((permission) => permission.code === code)?.scope_behavior).filter(Boolean));
    if (scopes.has('COMPANY_ONLY') && scopes.has('BRANCH_SCOPED')) return 'empresa + sucursal';
    if (scopes.has('BRANCH_SCOPED')) return 'por sucursal';
    if (scopes.has('COMPANY_ONLY')) return 'empresa';
    return 'sin permisos';
  }

  private loadContext(): void { this.beginLoad(); this.loadAudit(); this.api.context().subscribe({ next: (context) => { this.context.set(context); const current = this.selectedCompanyId(); const selected = context.companies.find((company) => company.id === current) ?? context.companies[0] ?? null; this.selectedCompanyId.set(selected?.id ?? null); if (selected) this.loadCompanyData(selected.id); else { this.loading.set(false); this.error.set('No hay empresas disponibles.'); } }, error: (error: unknown) => { this.loading.set(false); this.error.set(this.describeError(error, 'No fue posible cargar las empresas.')); } }); }
  private auditEndDate(): string {
    const end = new Date(`${this.auditToFilter}T00:00:00`);
    end.setDate(end.getDate() + 1);
    return end.toISOString();
  }

  loadAudit(): void {
    this.auditError.set('');
    this.api.audit({
      page: String(this.auditPage()),
      actor: this.auditActorFilter.trim(),
      event_type: this.auditEventFilter,
      resource_type: this.auditResourceFilter,
      company_id: this.auditCompanyFilter.trim(),
      from: this.auditFromFilter ? new Date(`${this.auditFromFilter}T00:00:00`).toISOString() : '',
      to: this.auditToFilter ? this.auditEndDate() : '',
      page_size: '100',
    }).subscribe({
      next: (response) => {
        this.auditEvents.set(response.events);
        this.auditTotal.set(response.total);
        this.auditHasNext.set(response.has_next);
      },
      error: (error: unknown) => {
        this.auditError.set(this.describeError(error, 'No se pudo cargar la auditoría.'));
        this.auditEvents.set([]);
        this.auditTotal.set(0);
        this.auditHasNext.set(false);
      },
    });
  }
  private loadCompanyData(companyId: number): void { this.beginLoad(); forkJoin({ overview: this.api.companyOverview(companyId), catalog: this.api.catalog(companyId), directories: this.api.directories(companyId) }).subscribe({ next: ({ overview, catalog, directories }) => { this.overview.set(overview); this.catalog.set(catalog); this.directories.set(directories); this.loading.set(false); }, error: (error: unknown) => { this.overview.set(null); this.loading.set(false); this.error.set(this.describeError(error, 'No fue posible cargar los mantenedores.')); } }); }
  private runMutation<T>(observable: Observable<T>, message: string, next: () => void): void {
    this.beginLoad();
    observable.subscribe({
      next: () => { this.notice.set(message); next(); },
      error: (error: unknown) => {
        this.loading.set(false);
        const detail = this.describeError(error, 'La operación no pudo completarse.');
        const current = this.dialog();
        if (current) this.dialog.set({ ...current, error: detail });
        else this.error.set(detail);
      },
    });
  }

  private executeDanger(danger: DangerState): void {
    this.loading.set(true);
    this.api.createDeleteChallenge(
      danger.companyId,
      danger.resourceType,
      danger.resourceId,
      danger.preview.confirmation_phrase,
      danger.reason,
    ).pipe(
      switchMap((challenge) => this.api.executeDeleteChallenge(
        danger.companyId,
        danger.resourceType,
        danger.resourceId,
        challenge.challenge_id,
        challenge.token,
        danger.preview.confirmation_phrase,
      )),
    ).subscribe({
      next: () => {
        this.loading.set(false);
        this.closeDanger();
        this.notice.set('Recurso eliminado permanentemente.');
        if (danger.resourceType === 'company') this.loadContext();
        else this.refresh();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        const current = this.danger();
        if (current) this.danger.set({ ...current, progress: 0, error: this.describeError(error, 'La eliminación no pudo completarse.') });
      },
    });
  }
  private beginLoad(): void {
    this.loading.set(true);
    this.clearStatus();
    const current = this.dialog();
    if (current?.error) this.dialog.set({ ...current, error: '' });
  }
  private clearStatus(): void { this.error.set(''); this.notice.set(''); }
  private rejectNonPlatform(): void { this.user.set(null); this.loading.set(false); this.error.set('Esta consola está disponible solo para administradores de plataforma.'); }
  private clearSession(): void { this.user.set(null); this.context.set(null); this.selectedCompanyId.set(null); this.overview.set(null); this.catalog.set({ categories: [], products: [], brands: [] }); this.directories.set({ suppliers: [], warehouses: [] }); this.auditEvents.set([]); this.auditTotal.set(0); this.auditHasNext.set(false); this.dialog.set(null); this.section.set('summary'); this.loading.set(false); this.clearStatus(); }
  private describeError(error: unknown, fallback: string): string { if (typeof error === 'object' && error !== null && 'error' in error) { const body = (error as { error?: { detail?: unknown; message?: unknown } }).error; if (typeof body?.detail === 'string') return body.detail; if (typeof body?.message === 'string') return body.message; if (body && typeof body === 'object') return Object.values(body).flat().filter((value): value is string => typeof value === 'string').join(' '); } return fallback; }
}
