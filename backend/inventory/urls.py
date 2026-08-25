from django.urls import path

from inventory import views


urlpatterns = [
    path(
        "stocks/",
        views.stock_list_create_view,
        name="inventory-stock-list-create",
    ),
    path(
        "movements/",
        views.movement_list_create_view,
        name="inventory-movement-list-create",
    ),
]
