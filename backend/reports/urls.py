from django.urls import path

from . import views


urlpatterns = [
    path("options/", views.report_options_view, name="report-options"),
    path("sales/", views.sales_report_view, name="sales-report"),
    path("sales/export/pdf/", views.sales_pdf_view, name="sales-report-pdf"),
    path("sales/export/xls/", views.sales_xls_view, name="sales-report-xls"),
    path("inventory/", views.inventory_report_view, name="inventory-report"),
    path("inventory/export/pdf/", views.inventory_pdf_view, name="inventory-report-pdf"),
    path("inventory/export/xls/", views.inventory_xls_view, name="inventory-report-xls"),
]
