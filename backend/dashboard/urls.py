from django.urls import path

from .views import dashboard_overview_view


urlpatterns = [
    path("overview/", dashboard_overview_view, name="dashboard-overview"),
]
