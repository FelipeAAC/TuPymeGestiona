from django.urls import path

from . import views


urlpatterns = [
    path("", views.document_list_create_view, name="electronic-tax-document-list-create"),
    path("<int:document_id>/", views.document_detail_view, name="electronic-tax-document-detail"),
    path("<int:document_id>/validate/", views.document_validate_view, name="electronic-tax-document-validate"),
    path("<int:document_id>/discard/", views.document_discard_view, name="electronic-tax-document-discard"),
    path("<int:document_id>/credit-notes/", views.document_credit_note_view, name="electronic-tax-document-credit-note"),
    path("<int:document_id>/debit-notes/", views.document_debit_note_view, name="electronic-tax-document-debit-note"),
    path("<int:document_id>/issue/", views.document_issue_view, name="electronic-tax-document-issue"),
    path("<int:document_id>/refresh-status/", views.document_refresh_status_view, name="electronic-tax-document-refresh-status"),
]
