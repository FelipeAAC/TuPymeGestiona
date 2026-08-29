from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.customer_list_create_view,
        name="customer-list-create",
    ),
    path(
        "<int:customer_id>/",
        views.customer_detail_view,
        name="customer-detail",
    ),
]
