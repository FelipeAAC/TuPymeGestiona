from django.contrib import admin
from django.urls import include, path

from config.views import health_check


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/auth/", include("accounts.urls")),
    path("api/organizations/", include("organizations.urls")),
    path("api/catalog/", include("catalog.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/customers/", include("customers.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/sales/", include("sales.urls")),
    path("api/v1/electronic-tax-documents/", include("electronic_tax.urls")),
    path("api/v1/folio-authorizations/", include("electronic_tax.folio_urls")),
    path("api/v1/electronic-tax-operations/", include("electronic_tax.operations_urls")),
    path("api/administration/", include("administration.urls")),
    path("api/portal/", include("portal.urls")),
    path("api/portal/payments/", include("external_payments.urls")),
]
