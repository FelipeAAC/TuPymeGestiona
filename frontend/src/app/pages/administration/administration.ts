import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Observable, Subscription } from 'rxjs';

import {
  AdminBranch,
  AdminOrderStatus,
  AdminPaymentMethod,
  AdminRole,
  AdminUser,
  AdministrationOverview,
  PaymentKind,
} from '../../core/administration/administration.models';
import { AdministrationService } from '../../core/administration/administration.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';


type AdministrationTab =
  | 'users'
  | 'roles'
  | 'company'
  | 'branches'
  | 'payments'
  | 'statuses'
  | 'settings'
  | 'audit';

type EditorKind = 'user' | 'role' | 'branch' | 'payment' | 'status' | 'company-create' | null;

@Component({
  selector: 'app-administration',
  imports: [ReactiveFormsModule],
  templateUrl: './administration.html',
  styleUrl: './administration.scss',
})
export class Administration implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly administrationService = inject(AdministrationService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private loadSubscription: Subscription | null = null;
  private saveSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly canAdminister = computed(() =>
    this.selectedMembership()?.permissions?.includes('administration.manage') ?? false,
  );

  readonly overview = signal<AdministrationOverview | null>(null);
  readonly activeTab = signal<AdministrationTab>('users');
  readonly editorKind = signal<EditorKind>(null);
  readonly editingId = signal<number | null>(null);
  readonly selectedRoleIds = signal<number[]>([]);
  readonly selectedBranchIds = signal<number[]>([]);
  readonly selectedPermissionCodes = signal<string[]>([]);

  readonly isLoading = signal(false);
  readonly isSaving = signal(false);
  readonly errorMessage = signal('');
  readonly editorError = signal('');
  readonly successMessage = signal('');
  readonly searchTerm = signal('');

  readonly users = computed(() => {
    const search = this.searchTerm().trim().toLocaleLowerCase('es');
    const users = this.overview()?.users ?? [];
    if (!search) return users;
    return users.filter((user) =>
      [user.username, user.email, user.first_name, user.last_name, ...user.role_names]
        .join(' ')
        .toLocaleLowerCase('es')
        .includes(search),
    );
  });

  readonly activeUsers = computed(
    () => (this.overview()?.users ?? []).filter((user) => user.status === 'ACTIVE').length,
  );
  readonly activeRoles = computed(
    () => (this.overview()?.roles ?? []).filter((role) => role.status === 'ACTIVE').length,
  );
  readonly activeBranches = computed(
    () => (this.overview()?.branches ?? []).filter((branch) => branch.is_active).length,
  );
  readonly activePaymentMethods = computed(
    () => (this.overview()?.payment_methods ?? []).filter((item) => item.is_active).length,
  );

  readonly userForm = this.formBuilder.group({
    username: ['', [Validators.maxLength(150)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    firstName: ['', [Validators.maxLength(150)]],
    lastName: ['', [Validators.maxLength(150)]],
    password: ['', [Validators.minLength(8), Validators.maxLength(128)]],
    status: 'ACTIVE',
  });

  readonly roleForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    status: 'ACTIVE',
  });

  readonly branchForm = this.formBuilder.group({
    code: ['', [Validators.required, Validators.maxLength(50)]],
    name: ['', [Validators.required, Validators.maxLength(150)]],
    address: ['', [Validators.maxLength(220)]],
    commune: ['', [Validators.maxLength(120)]],
    city: ['', [Validators.maxLength(120)]],
    phone: ['', [Validators.maxLength(40)]],
    isActive: true,
  });

  readonly paymentForm = this.formBuilder.group({
    code: ['', [Validators.required, Validators.maxLength(40)]],
    name: ['', [Validators.required, Validators.maxLength(100)]],
    kind: 'CASH' as PaymentKind,
    isActive: true,
    sortOrder: 10,
  });

  readonly statusForm = this.formBuilder.group({
    displayName: ['', [Validators.required, Validators.maxLength(80)]],
    sortOrder: 10,
    isActive: true,
  });

  readonly newCompanyForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    rut: ['', [Validators.maxLength(20)]],
    legalName: ['', [Validators.maxLength(180)]],
    businessActivity: ['', [Validators.maxLength(180)]],
    contactEmail: ['', [Validators.email, Validators.maxLength(254)]],
  });

  readonly companyForm = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    rut: ['', [Validators.maxLength(20)]],
    legalName: ['', [Validators.maxLength(180)]],
    businessActivity: ['', [Validators.maxLength(180)]],
    contactEmail: ['', [Validators.email, Validators.maxLength(254)]],
    phone: ['', [Validators.maxLength(40)]],
    address: ['', [Validators.maxLength(220)]],
    commune: ['', [Validators.maxLength(120)]],
    city: ['', [Validators.maxLength(120)]],
    isActive: true,
  });

  readonly settingsForm = this.formBuilder.group({
    vatRate: ['19.00', [Validators.required]],
    currency: ['CLP', [Validators.required, Validators.minLength(3), Validators.maxLength(3)]],
    timezone: ['America/Santiago', [Validators.required, Validators.maxLength(80)]],
    paymentProvider: ['MERCADO_PAGO', [Validators.required, Validators.maxLength(60)]],
    paymentSandboxEnabled: true,
    notificationSenderEmail: ['', [Validators.email, Validators.maxLength(254)]],
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();
      this.cancelRequests();
      this.overview.set(null);
      this.errorMessage.set('');
      this.successMessage.set('');
      this.closeEditor();

      if (membership && membership.permissions?.includes('administration.manage')) {
        this.loadOverview(membership.company.id);
      }

      onCleanup(() => this.cancelRequests());
    });
  }

  ngOnDestroy(): void {
    this.cancelRequests();
  }

  selectTab(tab: AdministrationTab): void {
    this.activeTab.set(tab);
    this.closeEditor();
    this.successMessage.set('');
  }

  updateSearch(event: Event): void {
    this.searchTerm.set((event.target as HTMLInputElement).value);
  }

  openCreateCompany(): void {
    this.editorKind.set('company-create');
    this.editingId.set(null);
    this.editorError.set('');
    this.newCompanyForm.reset({
      name: '',
      rut: '',
      legalName: '',
      businessActivity: '',
      contactEmail: '',
    });
  }

  openUser(user?: AdminUser): void {
    this.editorKind.set('user');
    this.editingId.set(user?.id ?? null);
    this.editorError.set('');
    this.selectedRoleIds.set(user?.role_ids ?? []);
    this.selectedBranchIds.set(user?.branch_ids ?? []);
    this.userForm.reset({
      username: user?.username ?? '',
      email: user?.email ?? '',
      firstName: user?.first_name ?? '',
      lastName: user?.last_name ?? '',
      password: '',
      status: user?.status ?? 'ACTIVE',
    });
    if (user) {
      this.userForm.controls.username.disable();
      this.userForm.controls.email.disable();
      this.userForm.controls.password.disable();
    } else {
      this.userForm.controls.username.enable();
      this.userForm.controls.email.enable();
      this.userForm.controls.password.enable();
    }
  }

  openRole(role?: AdminRole): void {
    this.editorKind.set('role');
    this.editingId.set(role?.id ?? null);
    this.editorError.set('');
    this.selectedPermissionCodes.set(role?.permission_codes ?? []);
    this.roleForm.reset({ name: role?.name ?? '', status: role?.status ?? 'ACTIVE' });
  }

  openBranch(branch?: AdminBranch): void {
    this.editorKind.set('branch');
    this.editingId.set(branch?.id ?? null);
    this.editorError.set('');
    this.branchForm.reset({
      code: branch?.code ?? '',
      name: branch?.name ?? '',
      address: branch?.address ?? '',
      commune: branch?.commune ?? '',
      city: branch?.city ?? '',
      phone: branch?.phone ?? '',
      isActive: branch?.is_active ?? true,
    });
  }

  openPayment(method?: AdminPaymentMethod): void {
    this.editorKind.set('payment');
    this.editingId.set(method?.id ?? null);
    this.editorError.set('');
    this.paymentForm.reset({
      code: method?.code ?? '',
      name: method?.name ?? '',
      kind: method?.kind ?? 'CASH',
      isActive: method?.is_active ?? true,
      sortOrder: method?.sort_order ?? 10,
    });
  }

  openStatus(item: AdminOrderStatus): void {
    this.editorKind.set('status');
    this.editingId.set(item.id);
    this.editorError.set('');
    this.statusForm.reset({
      displayName: item.display_name,
      sortOrder: item.sort_order,
      isActive: item.is_active,
    });
  }

  closeEditor(): void {
    if (this.isSaving()) return;
    this.editorKind.set(null);
    this.editingId.set(null);
    this.editorError.set('');
    this.selectedRoleIds.set([]);
    this.selectedBranchIds.set([]);
    this.selectedPermissionCodes.set([]);
  }

  toggleRole(roleId: number): void {
    this.selectedRoleIds.update((items) => this.toggleNumber(items, roleId));
  }

  toggleBranch(branchId: number): void {
    this.selectedBranchIds.update((items) => this.toggleNumber(items, branchId));
  }

  togglePermission(code: string): void {
    this.selectedPermissionCodes.update((items) =>
      items.includes(code) ? items.filter((item) => item !== code) : [...items, code],
    );
  }

  saveEditor(): void {
    const kind = this.editorKind();
    if (kind === 'user') this.saveUser();
    if (kind === 'role') this.saveRole();
    if (kind === 'branch') this.saveBranch();
    if (kind === 'payment') this.savePayment();
    if (kind === 'status') this.saveStatus();
    if (kind === 'company-create') this.saveNewCompany();
  }

  private saveNewCompany(): void {
    if (this.newCompanyForm.invalid || this.isSaving()) {
      this.newCompanyForm.markAllAsTouched();
      return;
    }
    const value = this.newCompanyForm.getRawValue();
    this.saveSubscription?.unsubscribe();
    this.editorError.set('');
    this.successMessage.set('');
    this.isSaving.set(true);
    this.saveSubscription = this.administrationService
      .createCompany({
        name: value.name.trim(),
        rut: value.rut.trim(),
        legal_name: value.legalName.trim(),
        business_activity: value.businessActivity.trim(),
        contact_email: value.contactEmail.trim(),
        is_active: true,
      })
      .pipe(finalize(() => this.isSaving.set(false)))
      .subscribe({
        next: (company) => {
          this.editorKind.set(null);
          this.successMessage.set(`Empresa "${company.name}" creada correctamente.`);
          this.organizationContextService.load().subscribe({
            next: (memberships) => {
              const membership = memberships.find((item) => item.company.id === company.id);
              if (membership) this.organizationContextService.selectMembership(membership.id);
            },
          });
        },
        error: (error: HttpErrorResponse) => this.editorError.set(this.errorText(error)),
      });
  }

  saveCompany(): void {
    const companyId = this.companyId();
    if (!companyId || this.companyForm.invalid || this.isSaving()) {
      this.companyForm.markAllAsTouched();
      return;
    }
    const value = this.companyForm.getRawValue();
    this.runSave(
      this.administrationService.updateCompany(companyId, {
        name: value.name.trim(),
        rut: value.rut.trim(),
        legal_name: value.legalName.trim(),
        business_activity: value.businessActivity.trim(),
        contact_email: value.contactEmail.trim(),
        phone: value.phone.trim(),
        address: value.address.trim(),
        commune: value.commune.trim(),
        city: value.city.trim(),
        is_active: value.isActive,
      }),
      'Datos de la empresa actualizados.',
    );
  }

  saveSettings(): void {
    const companyId = this.companyId();
    if (!companyId || this.settingsForm.invalid || this.isSaving()) {
      this.settingsForm.markAllAsTouched();
      return;
    }
    const value = this.settingsForm.getRawValue();
    this.runSave(
      this.administrationService.updateSettings(companyId, {
        vat_rate: value.vatRate.trim(),
        currency: value.currency.trim().toUpperCase(),
        timezone: value.timezone.trim(),
        payment_provider: value.paymentProvider.trim().toUpperCase(),
        payment_sandbox_enabled: value.paymentSandboxEnabled,
        notification_sender_email: value.notificationSenderEmail.trim(),
      }),
      'Parámetros generales actualizados.',
    );
  }

  roleChecked(roleId: number): boolean {
    return this.selectedRoleIds().includes(roleId);
  }

  branchChecked(branchId: number): boolean {
    return this.selectedBranchIds().includes(branchId);
  }

  permissionChecked(code: string): boolean {
    return this.selectedPermissionCodes().includes(code);
  }

  branchNames(ids: number[]): string {
    const branches = this.overview()?.branches ?? [];
    const names = ids.map((id) => branches.find((branch) => branch.id === id)?.name).filter(Boolean);
    return names.length ? names.join(', ') : 'Toda la empresa / sin restricción';
  }

  private saveUser(): void {
    const companyId = this.companyId();
    if (!companyId || this.userForm.invalid || this.isSaving()) {
      this.userForm.markAllAsTouched();
      return;
    }
    const value = this.userForm.getRawValue();
    const editingId = this.editingId();
    const input: Record<string, unknown> = {
      first_name: value.firstName.trim(),
      last_name: value.lastName.trim(),
      status: value.status,
      role_ids: this.selectedRoleIds(),
      branch_ids: this.selectedBranchIds(),
    };
    if (!editingId) {
      input['username'] = value.username.trim();
      input['email'] = value.email.trim();
      input['password'] = value.password;
    }
    const request = editingId
      ? this.administrationService.updateUser(companyId, editingId, input)
      : this.administrationService.createUser(companyId, input);
    this.runSave(request, editingId ? 'Usuario actualizado.' : 'Usuario agregado a la empresa.');
  }

  private saveRole(): void {
    const companyId = this.companyId();
    if (!companyId || this.roleForm.invalid || this.isSaving()) {
      this.roleForm.markAllAsTouched();
      return;
    }
    const value = this.roleForm.getRawValue();
    const editingId = this.editingId();
    const input = {
      name: value.name.trim(),
      status: value.status,
      permission_codes: this.selectedPermissionCodes(),
    };
    const request = editingId
      ? this.administrationService.updateRole(companyId, editingId, input)
      : this.administrationService.createRole(companyId, input);
    this.runSave(request, editingId ? 'Rol actualizado.' : 'Rol creado.');
  }

  private saveBranch(): void {
    const companyId = this.companyId();
    if (!companyId || this.branchForm.invalid || this.isSaving()) {
      this.branchForm.markAllAsTouched();
      return;
    }
    const value = this.branchForm.getRawValue();
    const editingId = this.editingId();
    const input = {
      code: value.code.trim().toUpperCase(),
      name: value.name.trim(),
      address: value.address.trim(),
      commune: value.commune.trim(),
      city: value.city.trim(),
      phone: value.phone.trim(),
      is_active: value.isActive,
    };
    const request = editingId
      ? this.administrationService.updateBranch(companyId, editingId, input)
      : this.administrationService.createBranch(companyId, input);
    this.runSave(request, editingId ? 'Sucursal actualizada.' : 'Sucursal creada.');
  }

  private savePayment(): void {
    const companyId = this.companyId();
    if (!companyId || this.paymentForm.invalid || this.isSaving()) {
      this.paymentForm.markAllAsTouched();
      return;
    }
    const value = this.paymentForm.getRawValue();
    const editingId = this.editingId();
    const input = {
      code: value.code.trim().toUpperCase(),
      name: value.name.trim(),
      kind: value.kind,
      is_active: value.isActive,
      sort_order: value.sortOrder,
    };
    const request = editingId
      ? this.administrationService.updatePaymentMethod(companyId, editingId, input)
      : this.administrationService.createPaymentMethod(companyId, input);
    this.runSave(request, editingId ? 'Método de pago actualizado.' : 'Método de pago creado.');
  }

  private saveStatus(): void {
    const companyId = this.companyId();
    const statusId = this.editingId();
    if (!companyId || !statusId || this.statusForm.invalid || this.isSaving()) {
      this.statusForm.markAllAsTouched();
      return;
    }
    const value = this.statusForm.getRawValue();
    this.runSave(
      this.administrationService.updateOrderStatus(companyId, statusId, {
        display_name: value.displayName.trim(),
        sort_order: value.sortOrder,
        is_active: value.isActive,
      }),
      'Estado de pedido actualizado.',
    );
  }

  private runSave(request: Observable<unknown>, message: string): void {
    const companyId = this.companyId();
    if (!companyId) return;
    this.saveSubscription?.unsubscribe();
    this.editorError.set('');
    this.successMessage.set('');
    this.isSaving.set(true);
    this.saveSubscription = request.pipe(finalize(() => this.isSaving.set(false))).subscribe({
      next: () => {
        this.successMessage.set(message);
        this.editorKind.set(null);
        this.loadOverview(companyId, true);
      },
      error: (error: HttpErrorResponse) => this.editorError.set(this.errorText(error)),
    });
  }

  private loadOverview(companyId: number, preserveSuccess = false): void {
    this.loadSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.errorMessage.set('');
    if (!preserveSuccess) this.successMessage.set('');
    this.loadSubscription = this.administrationService
      .loadOverview(companyId)
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: (overview) => {
          if (this.companyId() !== companyId) return;
          this.overview.set(overview);
          this.companyForm.reset({
            name: overview.company.name,
            rut: overview.company.rut,
            legalName: overview.company.legal_name,
            businessActivity: overview.company.business_activity,
            contactEmail: overview.company.contact_email,
            phone: overview.company.phone,
            address: overview.company.address,
            commune: overview.company.commune,
            city: overview.company.city,
            isActive: overview.company.is_active,
          });
          this.settingsForm.reset({
            vatRate: overview.settings.vat_rate,
            currency: overview.settings.currency,
            timezone: overview.settings.timezone,
            paymentProvider: overview.settings.payment_provider,
            paymentSandboxEnabled: overview.settings.payment_sandbox_enabled,
            notificationSenderEmail: overview.settings.notification_sender_email,
          });
        },
        error: (error: HttpErrorResponse) => {
          this.overview.set(null);
          this.errorMessage.set(this.errorText(error));
        },
      });
  }

  private companyId(): number | null {
    return this.selectedMembership()?.company.id ?? null;
  }

  private toggleNumber(items: number[], value: number): number[] {
    return items.includes(value) ? items.filter((item) => item !== value) : [...items, value];
  }

  private errorText(error: HttpErrorResponse): string {
    if (error.status === 0) return 'No fue posible conectar con el servidor.';
    if (error.status === 403 || error.status === 404) return error.error?.detail ?? 'No tienes permiso para esta operación.';
    if (error.status === 409) return error.error?.detail ?? 'La operación entra en conflicto con el estado actual.';
    const payload = error.error;
    if (payload && typeof payload === 'object') {
      for (const value of Object.values(payload)) {
        if (Array.isArray(value) && value.length) return String(value[0]);
        if (typeof value === 'string') return value;
      }
    }
    return 'No pudimos completar la operación. Revisa los datos e inténtalo nuevamente.';
  }

  private cancelRequests(): void {
    this.loadSubscription?.unsubscribe();
    this.saveSubscription?.unsubscribe();
    this.loadSubscription = null;
    this.saveSubscription = null;
  }
}
