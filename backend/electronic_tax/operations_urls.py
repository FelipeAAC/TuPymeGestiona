from django.urls import path

from . import operations_views


urlpatterns = [
    path("summary/", operations_views.operations_summary_view, name="electronic-tax-operations-summary"),
    path("alerts/", operations_views.operations_alerts_view, name="electronic-tax-operations-alerts"),
]
