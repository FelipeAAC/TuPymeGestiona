from django.urls import path

from . import views


urlpatterns = [
    path("summary/", views.folio_summary_view, name="folio-authorization-summary"),
    path("import/", views.folio_import_view, name="folio-authorization-import"),
]
