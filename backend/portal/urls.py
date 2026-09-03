from django.urls import path

from . import views

urlpatterns = [
    path("stores/", views.store_list_view, name="portal-store-list"),
    path("stores/<int:company_id>/catalog/", views.catalog_view, name="portal-catalog"),
    path("stores/<int:company_id>/products/<int:product_id>/", views.product_detail_view, name="portal-product-detail"),
    path("register/", views.register_view, name="portal-register"),
    path("account/", views.account_view, name="portal-account"),
    path("orders/", views.order_history_view, name="portal-order-history"),
    path("orders/create/", views.create_order_view, name="portal-order-create"),
    path("orders/<int:order_id>/", views.order_detail_view, name="portal-order-detail"),
]
