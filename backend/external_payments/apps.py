from django.apps import AppConfig


class ExternalPaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "external_payments"
    verbose_name = "Pagos externos"
