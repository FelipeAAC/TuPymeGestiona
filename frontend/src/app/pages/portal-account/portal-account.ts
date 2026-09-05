import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { finalize, forkJoin } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

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
  private readonly authService = inject(AuthService);
  private readonly organizationContextService = inject(OrganizationContextService);
  private readonly router = inject(Router);

  readonly currentUser = this.authService.currentUser;
  readonly memberships = this.organizationContextService.memberships;
  readonly hasActiveMembership = computed(() =>
    this.memberships().some((membership) => membership.status === 'ACTIVE'),
  );
  readonly displayName = computed(() => {
    const user = this.currentUser();
    if (!user) return '';
    return user.first_name.trim() || user.username || user.email;
  });
  readonly accounts = signal<PortalAccount[]>([]);
  readonly orders = signal<PortalOrder[]>([]);
  readonly payments = signal<PortalMercadoPagoPayment[]>([]);
  readonly selectedOrder = signal<PortalOrder | null>(null);
  readonly isLoading = signal(false);
  readonly isOrganizationContextLoading = signal(false);
  readonly isLoggingOut = signal(false);
  readonly payingOrderId = signal<number | null>(null);
  readonly errorMessage = signal('');
  readonly paymentMessage = signal('');

  ngOnInit(): void {
    this.loadOrganizationContext();
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

  logout(): void {
    if (this.isLoggingOut()) return;
    this.isLoggingOut.set(true);
    this.authService
      .logout()
      .pipe(finalize(() => this.isLoggingOut.set(false)))
      .subscribe({
        next: () => {
          this.organizationContextService.clear();
          void this.router.navigate(['/portal']);
        },
        error: () => this.errorMessage.set('No pudimos cerrar sesión. Inténtalo nuevamente.'),
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

  private loadOrganizationContext(): void {
    this.isOrganizationContextLoading.set(true);
    this.organizationContextService
      .load()
      .pipe(finalize(() => this.isOrganizationContextLoading.set(false)))
      .subscribe({
        error: () => this.organizationContextService.clear(),
      });
  }

  private upsertPayment(payment: PortalMercadoPagoPayment): void {
    const next = this.payments().filter((item) => item.order !== payment.order);
    this.payments.set([payment, ...next]);
  }
}
