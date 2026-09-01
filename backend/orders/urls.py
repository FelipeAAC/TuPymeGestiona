from django.urls import path

from . import views


urlpatterns = [
    path(
        "options/",
        views.order_options_view,
        name="order-options",
    ),
    path(
        "",
        views.order_list_create_view,
        name="order-list-create",
    ),
    path(
        "<int:order_id>/",
        views.order_detail_view,
        name="order-detail",
    ),
    path(
        "<int:order_id>/confirm/",
        views.order_confirm_view,
        name="order-confirm",
    ),
    path(
        "<int:order_id>/prepare/",
        views.order_prepare_view,
        name="order-prepare",
    ),
    path(
        "<int:order_id>/deliver/",
        views.order_deliver_view,
        name="order-deliver",
    ),
    path(
        "<int:order_id>/cancel/",
        views.order_cancel_view,
        name="order-cancel",
    ),
]
