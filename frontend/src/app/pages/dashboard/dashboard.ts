import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, OnDestroy, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize, Subscription } from 'rxjs';

import { DashboardOverviewResponse } from '../../core/dashboard/dashboard.models';
import { DashboardService } from '../../core/dashboard/dashboard.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnDestroy {
  private readonly dashboardService = inject(DashboardService);
  private readonly organizationContextService = inject(OrganizationContextService);
  private overviewSubscription: Subscription | null = null;

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly overview = signal<DashboardOverviewResponse | null>(null);
  readonly isLoading = signal(false);
  readonly errorMessage = signal('');

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();
      untracked(() => {
        this.cancelRequest();
        this.overview.set(null);
        this.errorMessage.set('');
        if (membership) {
          this.loadOverview(membership.company.id);
        }
      });
      onCleanup(() => this.cancelRequest());
    });
  }

  ngOnDestroy(): void {
    this.cancelRequest();
  }

  formatMoney(value: string | null): string {
    if (value === null) return '—';
    return new Intl.NumberFormat('es-CL', {
      style: 'currency',
      currency: 'CLP',
      maximumFractionDigits: 0,
    }).format(Number(value));
  }

  formatNumber(value: number | null): string {
    return value === null ? '—' : new Intl.NumberFormat('es-CL').format(value);
  }

  formatDate(value: string): string {
    return new Intl.DateTimeFormat('es-CL', {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(value));
  }

  private loadOverview(companyId: number): void {
    this.isLoading.set(true);
    this.overviewSubscription = this.dashboardService
      .getOverview(companyId)
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: (overview) => this.overview.set(overview),
        error: (error: HttpErrorResponse) => {
          this.overview.set(null);
          this.errorMessage.set(
            this.errorText(error, 'No pudimos cargar los indicadores del Dashboard.'),
          );
        },
      });
  }

  private errorText(error: HttpErrorResponse, fallback: string): string {
    const detail = typeof error.error?.detail === 'string' ? error.error.detail : '';
    return detail || fallback;
  }

  private cancelRequest(): void {
    this.overviewSubscription?.unsubscribe();
    this.overviewSubscription = null;
  }
}
