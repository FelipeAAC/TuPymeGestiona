import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import {
  Customer,
  CustomerInput,
  CustomerListQuery,
  CustomerOrdering,
  CustomerPagination,
  CustomerStatus,
} from '../../core/customers/customers.models';
import { CustomersService } from '../../core/customers/customers.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { CustomerEditor } from './customer-editor/customer-editor';

const EMPTY_PAGINATION: CustomerPagination = {
  count: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
  next_page: null,
  previous_page: null,
};

@Component({
  selector: 'app-customers',
  imports: [CustomerEditor, DatePipe, ReactiveFormsModule],
  templateUrl: './customers.html',
  styleUrl: './customers.scss',
})
export class Customers implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly customersService = inject(CustomersService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private listSubscription: Subscription | null = null;
  private saveSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly customers = signal<Customer[]>([]);
  readonly pagination = signal<CustomerPagination>({ ...EMPTY_PAGINATION });
  readonly canManageCustomers = signal(false);

  readonly isLoading = signal(false);
  readonly isSaving = signal(false);
  readonly isEditorOpen = signal(false);
  readonly editingCustomer = signal<Customer | null>(null);

  readonly listErrorMessage = signal('');
  readonly saveErrorMessage = signal('');
  readonly successMessage = signal('');

  readonly activeCustomersOnPage = computed(
    () => this.customers().filter((customer) => customer.status === 'ACTIVE').length,
  );
  readonly inactiveCustomersOnPage = computed(
    () => this.customers().filter((customer) => customer.status === 'INACTIVE').length,
  );
  readonly firstVisibleCustomer = computed(() => {
    const pagination = this.pagination();

    if (pagination.count === 0 || this.customers().length === 0) {
      return 0;
    }

    return (pagination.page - 1) * pagination.page_size + 1;
  });
  readonly lastVisibleCustomer = computed(() => {
    if (this.customers().length === 0) {
      return 0;
    }

    return this.firstVisibleCustomer() + this.customers().length - 1;
  });

  readonly filterForm = this.formBuilder.group({
    search: ['', [Validators.maxLength(150)]],
    status: this.formBuilder.control<CustomerStatus | ''>(''),
    ordering: this.formBuilder.control<CustomerOrdering>('name'),
    pageSize: this.formBuilder.control(10, [Validators.min(1), Validators.max(100)]),
  });

  readonly customerForm = this.formBuilder.group({
    code: ['', [Validators.required, Validators.maxLength(50)]],
    name: ['', [Validators.required, Validators.maxLength(150)]],
    taxId: ['', [Validators.maxLength(50)]],
    email: ['', [Validators.email, Validators.maxLength(254)]],
    phone: ['', [Validators.maxLength(50)]],
    status: this.formBuilder.control<CustomerStatus>('ACTIVE', [Validators.required]),
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.cancelRequests();
      this.customers.set([]);
      this.pagination.set({ ...EMPTY_PAGINATION });
      this.canManageCustomers.set(false);
      this.isLoading.set(false);
      this.isSaving.set(false);
      this.listErrorMessage.set('');
      this.saveErrorMessage.set('');
      this.successMessage.set('');
      this.closeEditor();
      this.resetFilters();

      if (membership) {
        this.loadCustomers(membership.company.id, 1);
      }

      onCleanup(() => this.cancelRequests());
    });
  }

  ngOnDestroy(): void {
    this.cancelRequests();
  }

  applyFilters(): void {
    const membership = this.selectedMembership();

    if (!membership || this.filterForm.invalid) {
      this.filterForm.markAllAsTouched();
      return;
    }

    this.successMessage.set('');
    this.loadCustomers(membership.company.id, 1);
  }

  clearFilters(): void {
    const membership = this.selectedMembership();

    this.resetFilters();
    this.successMessage.set('');

    if (membership) {
      this.loadCustomers(membership.company.id, 1);
    }
  }

  goToPage(page: number | null): void {
    const membership = this.selectedMembership();
    const pagination = this.pagination();

    if (
      !membership ||
      page === null ||
      page < 1 ||
      page > Math.max(pagination.total_pages, 1) ||
      page === pagination.page ||
      this.isLoading()
    ) {
      return;
    }

    this.loadCustomers(membership.company.id, page);
  }

  openCreateEditor(): void {
    if (!this.canManageCustomers()) {
      return;
    }

    this.editingCustomer.set(null);
    this.saveErrorMessage.set('');
    this.customerForm.reset({
      code: '',
      name: '',
      taxId: '',
      email: '',
      phone: '',
      status: 'ACTIVE',
    });
    this.isEditorOpen.set(true);
  }

  openEditEditor(customer: Customer): void {
    if (!this.canManageCustomers()) {
      return;
    }

    this.editingCustomer.set(customer);
    this.saveErrorMessage.set('');
    this.customerForm.reset({
      code: customer.code,
      name: customer.name,
      taxId: customer.tax_id,
      email: customer.email,
      phone: customer.phone,
      status: customer.status,
    });
    this.isEditorOpen.set(true);
  }

  closeEditor(): void {
    if (this.isSaving()) {
      return;
    }

    this.isEditorOpen.set(false);
    this.editingCustomer.set(null);
    this.saveErrorMessage.set('');
    this.customerForm.reset({
      code: '',
      name: '',
      taxId: '',
      email: '',
      phone: '',
      status: 'ACTIVE',
    });
  }

  saveCustomer(): void {
    const membership = this.selectedMembership();

    if (!membership || !this.canManageCustomers() || this.isSaving()) {
      return;
    }

    if (this.customerForm.invalid) {
      this.customerForm.markAllAsTouched();
      return;
    }

    const value = this.customerForm.getRawValue();
    const input: CustomerInput = {
      code: value.code.trim(),
      name: value.name.trim(),
      tax_id: value.taxId.trim(),
      email: value.email.trim(),
      phone: value.phone.trim(),
      status: value.status,
    };

    if (!input.code || !input.name) {
      if (!input.code) {
        this.customerForm.controls.code.setErrors({ required: true });
        this.customerForm.controls.code.markAsTouched();
      }

      if (!input.name) {
        this.customerForm.controls.name.setErrors({ required: true });
        this.customerForm.controls.name.markAsTouched();
      }

      return;
    }

    const companyId = membership.company.id;
    const editingCustomer = this.editingCustomer();
    const request = editingCustomer
      ? this.customersService.updateCustomer(companyId, editingCustomer.id, input)
      : this.customersService.createCustomer(companyId, input);

    this.saveSubscription?.unsubscribe();
    this.saveErrorMessage.set('');
    this.successMessage.set('');
    this.isSaving.set(true);

    this.saveSubscription = request
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isSaving.set(false);
          }
        }),
      )
      .subscribe({
        next: (customer) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.isEditorOpen.set(false);
          this.editingCustomer.set(null);
          this.successMessage.set(
            editingCustomer
              ? `Cliente "${customer.name}" actualizado correctamente.`
              : `Cliente "${customer.name}" creado correctamente.`,
          );
          this.loadCustomers(companyId, editingCustomer ? this.pagination().page : 1);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.handleSaveError(error);
        },
      });
  }

  customerInitials(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join('');
  }

  private loadCustomers(companyId: number, page: number): void {
    this.listSubscription?.unsubscribe();
    this.isLoading.set(true);
    this.listErrorMessage.set('');

    const filterValue = this.filterForm.getRawValue();
    const query: CustomerListQuery = {
      search: filterValue.search.trim() || undefined,
      status: filterValue.status || undefined,
      ordering: filterValue.ordering,
      page,
      page_size: filterValue.pageSize,
    };

    this.listSubscription = this.customersService
      .listCustomers(companyId, query)
      .pipe(
        finalize(() => {
          if (this.selectedMembership()?.company.id === companyId) {
            this.isLoading.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.customers.set(response.customers);
          this.pagination.set(response.pagination);
          this.canManageCustomers.set(true);
        },
        error: (error: HttpErrorResponse) => {
          if (this.selectedMembership()?.company.id !== companyId) {
            return;
          }

          this.customers.set([]);
          this.pagination.set({ ...EMPTY_PAGINATION, page_size: query.page_size });

          if (error.status === 403) {
            this.canManageCustomers.set(false);
            this.listErrorMessage.set(
              'No tienes permiso para administrar los clientes de esta empresa.',
            );
            return;
          }

          if (error.status === 0) {
            this.listErrorMessage.set(
              'No fue posible conectar con el servidor. Inténtalo nuevamente.',
            );
            return;
          }

          this.listErrorMessage.set('No pudimos cargar los clientes. Inténtalo nuevamente.');
        },
      });
  }

  private handleSaveError(error: HttpErrorResponse): void {
    if (error.status === 400) {
      const codeError = this.firstApiError(error, 'code');
      const emailError = this.firstApiError(error, 'email');

      this.saveErrorMessage.set(
        codeError || emailError || 'No pudimos guardar el cliente. Revisa los datos ingresados.',
      );
      return;
    }

    if (error.status === 403) {
      this.canManageCustomers.set(false);
      this.saveErrorMessage.set(
        'Ya no tienes permiso para administrar los clientes de esta empresa.',
      );
      return;
    }

    if (error.status === 404) {
      this.saveErrorMessage.set('El cliente ya no existe en esta empresa.');
      return;
    }

    if (error.status === 0) {
      this.saveErrorMessage.set('No fue posible conectar con el servidor. Inténtalo nuevamente.');
      return;
    }

    this.saveErrorMessage.set('No pudimos guardar el cliente. Inténtalo nuevamente.');
  }

  private firstApiError(error: HttpErrorResponse, field: string): string {
    const value = error.error?.[field];

    if (Array.isArray(value) && typeof value[0] === 'string') {
      return value[0];
    }

    if (typeof value === 'string') {
      return value;
    }

    return '';
  }

  private resetFilters(): void {
    this.filterForm.reset({
      search: '',
      status: '',
      ordering: 'name',
      pageSize: 10,
    });
  }

  private cancelRequests(): void {
    this.listSubscription?.unsubscribe();
    this.saveSubscription?.unsubscribe();
    this.listSubscription = null;
    this.saveSubscription = null;
  }
}
