import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { PortalMercadoPagoPayment } from '../../core/portal/portal.models';
import { PortalService } from '../../core/portal/portal.service';

@Component({
  selector: 'app-payment-result',
  imports: [RouterLink],
  templateUrl: './payment-result.html',
  styleUrl: './payment-result.scss',
})
export class PaymentResult implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly portalService = inject(PortalService);
  readonly payment = signal<PortalMercadoPagoPayment | null>(null);
  readonly isLoading = signal(true);
  readonly message = signal('Verificando el resultado directamente con Mercado Pago...');

  ngOnInit(): void {
    const orderId = Number(this.route.snapshot.queryParamMap.get('order') ?? '0');
    const paymentId = this.route.snapshot.queryParamMap.get('payment_id') ?? '';
    if (!orderId) {
      this.isLoading.set(false);
      this.message.set('No pudimos identificar el pedido del retorno.');
      return;
    }
    const request = paymentId
      ? this.portalService.refreshMercadoPagoPayment(orderId, paymentId)
      : this.portalService.getMercadoPagoPayment(orderId);
    request.pipe(finalize(() => this.isLoading.set(false))).subscribe({
      next: (payment) => {
        this.payment.set(payment);
        this.message.set(payment ? this.statusText(payment.status) : 'El pedido aún no registra un checkout de Mercado Pago.');
      },
      error: (error: HttpErrorResponse) =>
        this.message.set(error.error?.detail ?? 'No fue posible confirmar el resultado del pago.'),
    });
  }

  private statusText(status: PortalMercadoPagoPayment['status']): string {
    return ({
      CREATING: 'Estamos preparando el checkout.',
      READY: 'El checkout sigue disponible para completar el pago.',
      PENDING: 'Mercado Pago informa que el pago está pendiente.',
      APPROVED: 'Pago aprobado y verificado por el servidor.',
      REJECTED: 'Mercado Pago rechazó el pago. Puedes intentarlo nuevamente.',
      CANCELLED: 'El pago fue cancelado.',
      REFUNDED: 'El pago fue devuelto.',
      UNCERTAIN: 'El resultado todavía requiere verificación antes de cualquier reintento.',
    } as const)[status];
  }
}
