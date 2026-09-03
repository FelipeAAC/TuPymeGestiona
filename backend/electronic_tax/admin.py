from django.contrib import admin

from .models import (
    ElectronicTaxDocument,
    ElectronicTaxEvent,
    ElectronicTaxLine,
    ElectronicTaxReference,
    FolioAuthorization,
    FolioReservation,
    IdempotencyRecord,
    TaxCompanyProfile,
    TaxCustomerProfile,
    TaxProductProfile,
)


admin.site.register(TaxCompanyProfile)
admin.site.register(TaxCustomerProfile)
admin.site.register(TaxProductProfile)
admin.site.register(ElectronicTaxDocument)
admin.site.register(ElectronicTaxLine)
admin.site.register(ElectronicTaxReference)
admin.site.register(FolioAuthorization)
admin.site.register(FolioReservation)
admin.site.register(ElectronicTaxEvent)
admin.site.register(IdempotencyRecord)
