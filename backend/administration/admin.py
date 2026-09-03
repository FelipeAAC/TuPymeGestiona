from django.contrib import admin

from administration.models import AdministrationEvent, CompanySettings, OrderStatusConfiguration, PaymentMethod


admin.site.register(PaymentMethod)
admin.site.register(CompanySettings)
admin.site.register(OrderStatusConfiguration)
admin.site.register(AdministrationEvent)
