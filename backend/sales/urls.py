from django.urls import path

from . import views


urlpatterns = [
    path(
        "options/",
        views.sale_options_view,
        name="sale-options",
    ),
    path(
        "",
        views.sale_list_create_view,
        name="sale-list-create",
    ),
    path(
        "<int:sale_id>/",
        views.sale_detail_view,
        name="sale-detail",
    ),
    path(
        "<int:sale_id>/payments/",
        views.sale_payment_view,
        name="sale-payment",
    ),
    path(
        "<int:sale_id>/cancel/",
        views.sale_cancel_view,
        name="sale-cancel",
    ),
]
