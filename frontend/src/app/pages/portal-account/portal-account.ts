import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { finalize, forkJoin } from 'rxjs';

import {
  PortalAccount,
  PortalMercadoPagoPayment,
  PortalOrder,
} from '../../core/portal/portal.models';
import { PortalService } from '../../core/portal/portal.service';

@Component({
  selector: 'app-portal-account',
  imports: [RouterLink, DatePipe],
  templateUrl: './portal-account.html',
  styleUrl: './portal-account.scss',
})
export class PortalAccountPage implements OnInit {
  private readonly portalService = inject(PortalService);
  private readonly router = inject(Router);
  readonly accounts = signal<PortalAccount[]>([]);
  readonly orders = signal<PortalOrder[]>([]);
  readonly payments = signal<PortalMercadoPagoPayment[]>([]);
  readonly selectedOrder = signal<PortalOrder | null>(null);
  readonly isLoading = signal(false);
  readonly payingOrderId = signal<number | null>(null);
  readonly errorMessage = signal('');
  readonly paymentMessage = signal('');

  ngOnInit(): void {
    this.isLoading.set(true);
    forkJoin({
      accounts: this.portalService.getAccounts(),
      orders: this.portalService.getOrders(),
      payments: this.portalService.getMercadoPagoPayments(),
    })
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: ({ accounts, orders, payments }) => {
          this.accounts.set(accounts);
          this.orders.set(orders);
          this.payments.set(payments);
        },
        error: () => this.errorMessage.set('No pudimos cargar tu cuenta e historial.'),
      });
  }

  paymentFor(orderId: number): PortalMercadoPagoPayment | undefined {
    return this.payments().find((item) => item.order === orderId);
  }

  canPay(order: PortalOrder): boolean {
    const payment = this.paymentFor(order.id);
    return (
      (order.status === 'CONFIRMED' || order.status === 'PREPARED') &&
      payment?.status !== 'APPROVED' &&
      payment?.status !== 'REFUNDED'
    );
  }

  pay(order: PortalOrder): void {
    if (this.payingOrderId() !== null) return;
    const existing = this.paymentFor(order.id);
    if (existing?.checkout_url && ['READY', 'PENDING', 'REJECTED', 'CANCELLED'].includes(existing.status)) {
      window.location.assign(existing.checkout_url);
      return;
    }
    if (existing?.status === 'UNCERTAIN') {
      this.resolvePreference(order);
      return;
    }

    this.payingOrderId.set(order.id);
    this.paymentMessage.set('');
    this.portalService
      .createMercadoPagoPreference(order.id, crypto.randomUUID())
      .pipe(finalize(() => this.payingOrderId.set(null)))
      .subscribe({
        next: (payment) => {
          this.upsertPayment(payment);
          if (payment.checkout_url) window.location.assign(payment.checkout_url);
        },
        error: (error: HttpErrorResponse) => {
          this.paymentMessage.set(
            error.error?.detail ?? 'No fue posible iniciar Mercado Pago en este momento.',
          );
        },
      });
  }

  resolvePreference(order: PortalOrder): void {
    this.payingOrderId.set(order.id);
    this.portalService
      .resolveMercadoPagoPreference(order.id)
      .pipe(finalize(() => this.payingOrderId.set(null)))
      .subscribe({
        next: (payment) => {
          this.upsertPayment(payment);
          if (payment.checkout_url) window.location.assign(payment.checkout_url);
        },
        error: (error: HttpErrorResponse) =>
          this.paymentMessage.set(
            error.error?.detail ?? 'Aún no fue posible resolver la preferencia anterior.',
          ),
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

  paymentLabel(payment?: PortalMercadoPagoPayment): string {
    if (!payment) return 'Sin pago en línea';
    return ({
      CREATING: 'Preparando pago',
      READY: 'Listo para pagar',
      PENDING: 'Pago pendiente',
      APPROVED: 'Pago aprobado',
      REJECTED: 'Pago rechazado',
      CANCELLED: 'Pago cancelado',
      REFUNDED: 'Pago devuelto',
      UNCERTAIN: 'Pago por verificar',
    } as const)[payment.status];
  }

  private upsertPayment(payment: PortalMercadoPagoPayment): void {
    const next = this.payments().filter((item) => item.order !== payment.order);
    this.payments.set([payment, ...next]);
  }
}
