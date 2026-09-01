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
]
