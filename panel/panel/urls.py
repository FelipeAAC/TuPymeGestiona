from django.contrib import admin
from django.urls import path
from core.views import (
    dashboard, quick_add_product, quick_order, quick_message, restock
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard, name="dashboard"),
    path("add-product/", quick_add_product, name="add_product"),
    path("order/", quick_order, name="quick_order"),
    path("message/", quick_message, name="quick_message"),
    path("restock/", restock, name="restock"),
]
