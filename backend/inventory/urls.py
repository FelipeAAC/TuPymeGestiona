from django.urls import path

from inventory import views


urlpatterns = [
    path(
        "stocks/",
        views.stock_list_create_view,
        name="inventory-stock-list-create",
    ),
]
