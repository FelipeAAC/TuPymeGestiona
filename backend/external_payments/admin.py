from django.contrib import admin

from .models import MercadoPagoCheckout, MercadoPagoEvent, MercadoPagoRemotePayment, MercadoPagoWebhookReceipt

admin.site.register(MercadoPagoCheckout)
admin.site.register(MercadoPagoRemotePayment)
admin.site.register(MercadoPagoEvent)
admin.site.register(MercadoPagoWebhookReceipt)
