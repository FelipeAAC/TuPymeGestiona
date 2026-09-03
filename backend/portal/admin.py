from django.contrib import admin

from .models import CustomerPortalAccount, PortalOrderRequest

admin.site.register(CustomerPortalAccount)
admin.site.register(PortalOrderRequest)
