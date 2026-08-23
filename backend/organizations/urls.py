from django.urls import path

from organizations import views


urlpatterns = [
    path(
        "context/",
        views.organization_context_view,
        name="organization-context",
    ),
    path(
        "warehouses/",
        views.warehouse_list_create_view,
        name="warehouse-list-create",
    ),
]
