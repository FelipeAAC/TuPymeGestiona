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
]
