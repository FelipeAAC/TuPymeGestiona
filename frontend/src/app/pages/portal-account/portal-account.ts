import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { PortalAccount, PortalOrder } from '../../core/portal/portal.models';
import { PortalService } from '../../core/portal/portal.service';

@Component({
  selector: 'app-portal-account',
  imports: [RouterLink, DatePipe],
  templateUrl: './portal-account.html',
  styleUrl: './portal-account.scss',
})
export class PortalAccountPage implements OnInit {
  private readonly portalService = inject(PortalService);
  readonly accounts = signal<PortalAccount[]>([]);
  readonly orders = signal<PortalOrder[]>([]);
  readonly selectedOrder = signal<PortalOrder | null>(null);
  readonly isLoading = signal(false);
  readonly errorMessage = signal('');

  ngOnInit(): void {
    this.isLoading.set(true);
    this.portalService.getAccounts().subscribe({
      next: (accounts) => this.accounts.set(accounts),
      error: () => this.errorMessage.set('No pudimos cargar tu perfil.'),
    });
    this.portalService
      .getOrders()
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: (orders) => this.orders.set(orders),
        error: () => this.errorMessage.set('No pudimos cargar tu historial de pedidos.'),
      });
  }

  showDetail(order: PortalOrder): void {
    this.selectedOrder.set(order);
  }

  closeDetail(): void {
    this.selectedOrder.set(null);
  }

  statusLabel(status: PortalOrder['status']): string {
    return ({
      DRAFT: 'Borrador',
      CONFIRMED: 'Confirmado',
      PREPARED: 'En preparación',
      DELIVERED: 'Entregado',
      CANCELLED: 'Cancelado',
    } as const)[status];
  }
}
