from django.urls import path

from organizations import views


urlpatterns = [
    path(
        "context/",
        views.organization_context_view,
        name="organization-context",
    ),
]
