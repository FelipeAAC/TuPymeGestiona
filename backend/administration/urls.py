from django.urls import path

from administration import views


urlpatterns = [
    path("overview/", views.overview_view, name="administration-overview"),
    path("companies/", views.company_create_view, name="administration-company-create"),
    path("companies/<int:company_id>/", views.company_detail_view, name="administration-company-detail"),
    path("users/", views.user_list_create_view, name="administration-user-list-create"),
    path("users/<int:membership_id>/", views.user_detail_view, name="administration-user-detail"),
    path("roles/", views.role_list_create_view, name="administration-role-list-create"),
    path("roles/<int:role_id>/", views.role_detail_view, name="administration-role-detail"),
    path("branches/", views.branch_list_create_view, name="administration-branch-list-create"),
    path("branches/<int:branch_id>/", views.branch_detail_view, name="administration-branch-detail"),
    path("payment-methods/", views.payment_method_list_create_view, name="administration-payment-method-list-create"),
    path("payment-methods/<int:method_id>/", views.payment_method_detail_view, name="administration-payment-method-detail"),
    path("order-statuses/<int:status_id>/", views.order_status_detail_view, name="administration-order-status-detail"),
    path("settings/", views.company_settings_view, name="administration-settings"),
]
