import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, OnDestroy, signal, untracked } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import { OrganizationContextService } from '../../core/organization/organization-context.service';
import {
  InventoryReportQuery,
  InventoryReportResponse,
  ReportOptionsResponse,
  SalesReportQuery,
  SalesReportResponse,
  StockLevelFilter,
} from '../../core/reports/reports.models';
import { ReportsService } from '../../core/reports/reports.service';

@Component({
  selector: 'app-reports',
  imports: [ReactiveFormsModule],
  templateUrl: './reports.html',
  styleUrl: './reports.scss',
})
export class Reports implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly reportsService = inject(ReportsService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private optionsSubscription: Subscription | null = null;
  private salesSubscription: Subscription | null = null;
  private inventorySubscription: Subscription | null = null;
  private downloadSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly options = signal<ReportOptionsResponse | null>(null);
  readonly salesReport = signal<SalesReportResponse | null>(null);
  readonly inventoryReport = signal<InventoryReportResponse | null>(null);
  readonly activeTab = signal<'sales' | 'inventory'>('sales');

  readonly isLoadingOptions = signal(false);
  readonly isLoadingSales = signal(false);
  readonly isLoadingInventory = signal(false);
  readonly downloading = signal<string | null>(null);
  readonly errorMessage = signal('');

  readonly salesForm = this.formBuilder.group({
    dateFrom: '',
    dateTo: '',
    branchId: 0,
    sellerId: 0,
  });

  readonly inventoryForm = this.formBuilder.group({
    warehouseId: 0,
    categoryId: 0,
    stockLevel: this.formBuilder.control<StockLevelFilter>('ALL'),
    criticalThreshold: this.formBuilder.control(5, [Validators.required, Validators.min(0)]),
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();
      untracked(() => {
        this.cancelRequests();
        this.reset();
        if (membership) {
          this.loadOptions(membership.company.id);
        }
      });
      onCleanup(() => this.cancelRequests());
    });
  }

  ngOnDestroy(): void {
    this.cancelRequests();
  }

  selectTab(tab: 'sales' | 'inventory'): void {
    const opts = this.options();
    if (!opts) return;
    if (tab === 'sales' && !opts.permissions.sales) return;
    if (tab === 'inventory' && !opts.permissions.inventory) return;
    this.activeTab.set(tab);
  }

  generateSales(): void {
    const membership = this.selectedMembership();
    if (!membership || !this.options()?.permissions.sales || this.isLoadingSales()) return;
    const query = this.salesQuery();
    this.salesSubscription?.unsubscribe();
    this.errorMessage.set('');
    this.isLoadingSales.set(true);
    this.salesSubscription = this.reportsService
      .getSalesReport(membership.company.id, query)
      .pipe(finalize(() => this.isLoadingSales.set(false)))
      .subscribe({
        next: (report) => this.salesReport.set(report),
        error: (error: HttpErrorResponse) => {
          this.salesReport.set(null);
          this.errorMessage.set(this.errorText(error, 'No pudimos generar el reporte de ventas.'));
        },
      });
  }

  generateInventory(): void {
    const membership = this.selectedMembership();
    if (!membership || !this.options()?.permissions.inventory || this.isLoadingInventory()) return;
    if (this.inventoryForm.invalid) {
      this.inventoryForm.markAllAsTouched();
      return;
    }
    const query = this.inventoryQuery();
    this.inventorySubscription?.unsubscribe();
    this.errorMessage.set('');
    this.isLoadingInventory.set(true);
    this.inventorySubscription = this.reportsService
      .getInventoryReport(membership.company.id, query)
      .pipe(finalize(() => this.isLoadingInventory.set(false)))
      .subscribe({
        next: (report) => this.inventoryReport.set(report),
        error: (error: HttpErrorResponse) => {
          this.inventoryReport.set(null);
          this.errorMessage.set(this.errorText(error, 'No pudimos generar el reporte de inventario.'));
        },
      });
  }

  exportSales(format: 'pdf' | 'xls'): void {
    const membership = this.selectedMembership();
    if (!membership || !this.salesReport()?.rows.length || this.downloading()) return;
    this.downloading.set(`sales-${format}`);
    this.downloadSubscription = this.reportsService
      .downloadSales(membership.company.id, this.salesQuery(), format)
      .pipe(finalize(() => this.downloading.set(null)))
      .subscribe({
        next: (blob) => this.saveBlob(blob, `reporte_ventas_${membership.company.id}.${format === 'pdf' ? 'pdf' : 'xlsx'}`),
        error: (error: HttpErrorResponse) => this.errorMessage.set(this.errorText(error, 'No pudimos exportar el reporte de ventas.')),
      });
  }

  exportInventory(format: 'pdf' | 'xls'): void {
    const membership = this.selectedMembership();
    if (!membership || !this.inventoryReport()?.rows.length || this.downloading()) return;
    this.downloading.set(`inventory-${format}`);
    this.downloadSubscription = this.reportsService
      .downloadInventory(membership.company.id, this.inventoryQuery(), format)
      .pipe(finalize(() => this.downloading.set(null)))
      .subscribe({
        next: (blob) => this.saveBlob(blob, `reporte_inventario_${membership.company.id}.${format === 'pdf' ? 'pdf' : 'xlsx'}`),
        error: (error: HttpErrorResponse) => this.errorMessage.set(this.errorText(error, 'No pudimos exportar el reporte de inventario.')),
      });
  }

  formatMoney(value: string | number): string {
    return new Intl.NumberFormat('es-CL', {
      style: 'currency',
      currency: 'CLP',
      maximumFractionDigits: 0,
    }).format(Number(value));
  }

  formatQuantity(value: string | number): string {
    return new Intl.NumberFormat('es-CL', { maximumFractionDigits: 3 }).format(Number(value));
  }

  saleStatusLabel(status: string): string {
    return ({ PENDING: 'Pendiente', PARTIAL: 'Pago parcial', PAID: 'Pagada', CANCELLED: 'Anulada' } as Record<string, string>)[status] ?? status;
  }

  stockLevelLabel(level: string): string {
    return ({ OUT: 'Sin stock', CRITICAL: 'Crítico', AVAILABLE: 'Disponible' } as Record<string, string>)[level] ?? level;
  }

  private loadOptions(companyId: number): void {
    this.isLoadingOptions.set(true);
    this.optionsSubscription = this.reportsService
      .getOptions(companyId)
      .pipe(finalize(() => this.isLoadingOptions.set(false)))
      .subscribe({
        next: (options) => {
          this.options.set(options);
          if (options.permissions.sales) {
            this.activeTab.set('sales');
            this.generateSales();
          } else if (options.permissions.inventory) {
            this.activeTab.set('inventory');
            this.generateInventory();
          }
        },
        error: (error: HttpErrorResponse) => {
          this.errorMessage.set(this.errorText(error, 'No pudimos cargar las opciones de reportes.'));
        },
      });
  }

  private salesQuery(): SalesReportQuery {
    const value = this.salesForm.getRawValue();
    return {
      date_from: value.dateFrom || undefined,
      date_to: value.dateTo || undefined,
      branch: value.branchId || null,
      seller: value.sellerId || null,
    };
  }

  private inventoryQuery(): InventoryReportQuery {
    const value = this.inventoryForm.getRawValue();
    return {
      warehouse: value.warehouseId || null,
      category: value.categoryId || null,
      stock_level: value.stockLevel,
      critical_threshold: value.criticalThreshold,
    };
  }

  private saveBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  private errorText(error: HttpErrorResponse, fallback: string): string {
    const detail = typeof error.error?.detail === 'string' ? error.error.detail : '';
    return detail || fallback;
  }

  private reset(): void {
    this.options.set(null);
    this.salesReport.set(null);
    this.inventoryReport.set(null);
    this.errorMessage.set('');
    this.activeTab.set('sales');
    this.salesForm.reset({ dateFrom: '', dateTo: '', branchId: 0, sellerId: 0 });
    this.inventoryForm.reset({ warehouseId: 0, categoryId: 0, stockLevel: 'ALL', criticalThreshold: 5 });
  }

  private cancelRequests(): void {
    this.optionsSubscription?.unsubscribe();
    this.salesSubscription?.unsubscribe();
    this.inventorySubscription?.unsubscribe();
    this.downloadSubscription?.unsubscribe();
  }
}
