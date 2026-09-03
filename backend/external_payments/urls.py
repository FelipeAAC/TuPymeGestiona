from django.urls import path

from . import views

urlpatterns = [
    path("mercado-pago/", views.checkout_list_view, name="mp-checkout-list"),
    path("mercado-pago/webhook/", views.webhook_view, name="mp-webhook"),
    path("orders/<int:order_id>/mercado-pago/", views.checkout_detail_view, name="mp-checkout-detail"),
    path("orders/<int:order_id>/mercado-pago/preference/", views.create_preference_view, name="mp-create-preference"),
    path("orders/<int:order_id>/mercado-pago/resolve-preference/", views.resolve_preference_view, name="mp-resolve-preference"),
    path("orders/<int:order_id>/mercado-pago/refresh/", views.refresh_payment_view, name="mp-refresh-payment"),
]
