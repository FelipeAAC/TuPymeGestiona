import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from catalog.models import ProductVariant
from customers.models import Customer
from organizations.models import Branch, Company
from sales.models import Sale


class TaxCompanyProfile(models.Model):
    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="electronic_tax_profile",
    )
    rut = models.CharField(max_length=20)
    legal_name = models.CharField(max_length=150)
    business_activity = models.CharField(max_length=150)
    address = models.CharField(max_length=200)
    commune = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True, default="")
    tax_email = models.EmailField(blank=True, default="")
    economic_activity_code = models.PositiveIntegerField(null=True, blank=True)
    sii_resolution_number = models.PositiveIntegerField(null=True, blank=True)
    sii_resolution_date = models.DateField(null=True, blank=True)
    sii_regional_office = models.CharField(max_length=120, blank=True, default="")
    sii_branch_code = models.CharField(max_length=20, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id"]

    def __str__(self):
        return f"{self.company} - {self.rut}"


class TaxCustomerProfile(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.PROTECT,
        related_name="electronic_tax_profile",
    )
    rut = models.CharField(max_length=20)
    legal_name = models.CharField(max_length=150)
    business_activity = models.CharField(max_length=150)
    address = models.CharField(max_length=200)
    commune = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True, default="")
    tax_email = models.EmailField(blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["customer_id"]

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.company_id is None:
            raise ValidationError({"customer": "El cliente debe pertenecer a una empresa."})

    def __str__(self):
        return f"{self.customer} - {self.rut}"


class TaxProductProfile(models.Model):
    class TaxCategory(models.TextChoices):
        AFFECTED = "AFFECTED", "Afecto"
        EXEMPT = "EXEMPT", "Exento/no gravado"

    variant = models.OneToOneField(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="electronic_tax_profile",
    )
    tax_category = models.CharField(
        max_length=20,
        choices=TaxCategory.choices,
        default=TaxCategory.AFFECTED,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["variant_id"]

    def __str__(self):
        return f"{self.variant} - {self.tax_category}"


class FolioAuthorization(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        EXHAUSTED = "EXHAUSTED", "Agotado"
        DISABLED = "DISABLED", "Deshabilitado"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="folio_authorizations",
    )
    type_code = models.PositiveSmallIntegerField()
    start_folio = models.PositiveBigIntegerField()
    end_folio = models.PositiveBigIntegerField()
    next_folio = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    source_label = models.CharField(max_length=120, blank=True, default="")
    caf_hash = models.CharField(max_length=64, blank=True, default="")
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "type_code", "start_folio"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "type_code", "start_folio", "end_folio"],
                name="uniq_folio_authorization_range",
            ),
            models.CheckConstraint(
                condition=Q(start_folio__gt=0),
                name="folio_authorization_start_positive",
            ),
            models.CheckConstraint(
                condition=Q(end_folio__gte=models.F("start_folio")),
                name="folio_authorization_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=Q(next_folio__gte=models.F("start_folio")),
                name="folio_authorization_next_not_before_start",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.type_code not in ElectronicTaxDocument.TypeCode.values:
            errors["type_code"] = "El tipo de DTE no esta soportado por el MVP."
        if self.start_folio and self.end_folio and self.start_folio > self.end_folio:
            errors["end_folio"] = "El fin del rango no puede ser menor al inicio."
        if self.next_folio and self.start_folio and self.next_folio < self.start_folio:
            errors["next_folio"] = "El siguiente folio no puede ser menor al inicio."
        if self.next_folio and self.end_folio and self.next_folio > self.end_folio + 1:
            errors["next_folio"] = "El siguiente folio excede el rango autorizado."
        if self.company_id and self.type_code and self.start_folio and self.end_folio:
            overlap = FolioAuthorization.objects.filter(
                company_id=self.company_id,
                type_code=self.type_code,
                start_folio__lte=self.end_folio,
                end_folio__gte=self.start_folio,
            )
            if self.pk:
                overlap = overlap.exclude(pk=self.pk)
            if overlap.exists():
                errors["start_folio"] = "El rango de folios se superpone con otra autorizacion."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company} - DTE {self.type_code} {self.start_folio}-{self.end_folio}"


class ElectronicTaxDocument(models.Model):
    class TypeCode(models.IntegerChoices):
        INVOICE = 33, "Factura electronica"
        EXEMPT_INVOICE = 34, "Factura no afecta o exenta"
        DEBIT_NOTE = 56, "Nota de debito electronica"
        CREDIT_NOTE = 61, "Nota de credito electronica"

    class State(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        READY = "READY", "Listo"
        FOLIO_RESERVED = "FOLIO_RESERVED", "Folio reservado"
        SIGNED = "SIGNED", "Firmado"
        SUBMITTED = "SUBMITTED", "Enviado"
        PROCESSING = "PROCESSING", "Procesando"
        ACCEPTED = "ACCEPTED", "Aceptado"
        ACCEPTED_WITH_REPAIR = "ACCEPTED_WITH_REPAIR", "Aceptado con reparo"
        REJECTED = "REJECTED", "Rechazado"
        SEND_UNCERTAIN = "SEND_UNCERTAIN", "Envio incierto"
        VOIDED_PRE_SUBMISSION = "VOIDED_PRE_SUBMISSION", "Folio anulado antes de envio"
        CANCELLED_BY_REFERENCE = "CANCELLED_BY_REFERENCE", "Anulado por referencia"
        DISCARDED = "DISCARDED", "Descartado"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="electronic_tax_documents",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="electronic_tax_documents",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="electronic_tax_documents",
    )
    type_code = models.PositiveSmallIntegerField(choices=TypeCode.choices)
    state = models.CharField(max_length=32, choices=State.choices, default=State.DRAFT)
    version = models.PositiveIntegerField(default=1)
    is_active_base = models.BooleanField(default=False)

    issuer_rut = models.CharField(max_length=20)
    issuer_legal_name = models.CharField(max_length=150)
    issuer_business_activity = models.CharField(max_length=150)
    issuer_address = models.CharField(max_length=200)
    issuer_commune = models.CharField(max_length=100)
    issuer_city = models.CharField(max_length=100, blank=True, default="")
    issuer_tax_email = models.EmailField(blank=True, default="")

    receiver_rut = models.CharField(max_length=20)
    receiver_legal_name = models.CharField(max_length=150)
    receiver_business_activity = models.CharField(max_length=150)
    receiver_address = models.CharField(max_length=200)
    receiver_commune = models.CharField(max_length=100)
    receiver_city = models.CharField(max_length=100, blank=True, default="")
    receiver_tax_email = models.EmailField(blank=True, default="")

    net_amount = models.BigIntegerField(default=0)
    exempt_amount = models.BigIntegerField(default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("19.00"))
    vat_amount = models.BigIntegerField(default=0)
    total_amount = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="CLP")

    issue_date = models.DateField(null=True, blank=True)
    folio = models.PositiveBigIntegerField(null=True, blank=True)
    folio_authorization = models.ForeignKey(
        FolioAuthorization,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    provider_track_id = models.CharField(max_length=120, blank=True, default="")
    provider_status_code = models.CharField(max_length=80, blank=True, default="")
    provider_status_message = models.CharField(max_length=500, blank=True, default="")
    provider_last_checked_at = models.DateTimeField(null=True, blank=True)

    snapshot_hash = models.CharField(max_length=64)
    xml_hash = models.CharField(max_length=64, blank=True, default="")
    creation_idempotency_key = models.CharField(max_length=100)
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_electronic_tax_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    discarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["company_id", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "type_code", "folio"],
                condition=Q(folio__isnull=False),
                name="uniq_dte_company_type_folio",
            ),
            models.UniqueConstraint(
                fields=["company", "sale"],
                condition=Q(is_active_base=True),
                name="uniq_dte_active_base_per_sale",
            ),
            models.CheckConstraint(condition=Q(version__gt=0), name="dte_version_positive"),
            models.CheckConstraint(condition=Q(net_amount__gte=0), name="dte_net_not_negative"),
            models.CheckConstraint(condition=Q(exempt_amount__gte=0), name="dte_exempt_not_negative"),
            models.CheckConstraint(condition=Q(vat_amount__gte=0), name="dte_vat_not_negative"),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="dte_total_not_negative"),
        ]

    IMMUTABLE_FIELDS = (
        "company_id",
        "branch_id",
        "sale_id",
        "type_code",
        "issuer_rut",
        "issuer_legal_name",
        "issuer_business_activity",
        "issuer_address",
        "issuer_commune",
        "issuer_city",
        "issuer_tax_email",
        "receiver_rut",
        "receiver_legal_name",
        "receiver_business_activity",
        "receiver_address",
        "receiver_commune",
        "receiver_city",
        "receiver_tax_email",
        "net_amount",
        "exempt_amount",
        "vat_rate",
        "vat_amount",
        "total_amount",
        "currency",
        "snapshot_hash",
    )

    def clean(self):
        super().clean()
        errors = {}
        if self.company_id and self.branch_id and self.branch.company_id != self.company_id:
            errors["branch"] = "La sucursal debe pertenecer a la empresa del DTE."
        if self.company_id and self.sale_id and self.sale.company_id != self.company_id:
            errors["sale"] = "La venta debe pertenecer a la empresa del DTE."
        if self.branch_id and self.sale_id and self.sale.branch_id != self.branch_id:
            errors["sale"] = "La venta debe pertenecer a la sucursal del DTE."
        if self.currency != "CLP":
            errors["currency"] = "El MVP solo admite moneda CLP."
        if self.type_code in (self.TypeCode.INVOICE, self.TypeCode.EXEMPT_INVOICE):
            inactive_terminal_states = {
                self.State.DISCARDED,
                self.State.CANCELLED_BY_REFERENCE,
            }
            if not self.is_active_base and self.state not in inactive_terminal_states:
                errors["is_active_base"] = "Una factura base activa debe marcarse como tal."
        elif self.is_active_base:
            errors["is_active_base"] = "Las notas no pueden ser factura base activa."
        if errors:
            raise ValidationError(errors)

    def _assert_fiscal_immutability(self):
        if not self.pk:
            return
        original = ElectronicTaxDocument.objects.filter(pk=self.pk).first()
        if original is None:
            return
        locked_states = {
            self.State.FOLIO_RESERVED,
            self.State.SIGNED,
            self.State.SUBMITTED,
            self.State.PROCESSING,
            self.State.ACCEPTED,
            self.State.ACCEPTED_WITH_REPAIR,
            self.State.REJECTED,
            self.State.SEND_UNCERTAIN,
            self.State.VOIDED_PRE_SUBMISSION,
            self.State.CANCELLED_BY_REFERENCE,
        }
        if original.state not in locked_states:
            return
        changed = [field for field in self.IMMUTABLE_FIELDS if getattr(original, field) != getattr(self, field)]
        if changed:
            raise ValidationError({"state": "El contenido fiscal es inmutable desde FOLIO_RESERVED."})

    def save(self, *args, **kwargs):
        self._assert_fiscal_immutability()
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los DTE no se eliminan fisicamente; use una transicion trazable.")

    def __str__(self):
        folio = self.folio if self.folio is not None else "sin-folio"
        return f"{self.company} - DTE {self.type_code} {folio}"


class ElectronicTaxLine(models.Model):
    document = models.ForeignKey(
        ElectronicTaxDocument,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    line_number = models.PositiveIntegerField()
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="electronic_tax_lines",
        null=True,
        blank=True,
    )
    sku = models.CharField(max_length=100, blank=True, default="")
    description = models.CharField(max_length=250)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.BigIntegerField(default=0)
    tax_category = models.CharField(max_length=20, choices=TaxProductProfile.TaxCategory.choices)
    net_amount = models.BigIntegerField(default=0)
    exempt_amount = models.BigIntegerField(default=0)
    vat_amount = models.BigIntegerField(default=0)
    total_amount = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "line_number"]
        constraints = [
            models.UniqueConstraint(fields=["document", "line_number"], name="uniq_dte_line_number"),
            models.CheckConstraint(condition=Q(line_number__gt=0), name="dte_line_number_positive"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="dte_line_quantity_positive"),
            models.CheckConstraint(condition=Q(discount_amount__gte=0), name="dte_line_discount_not_negative"),
        ]

    def _assert_editable(self):
        if self.document.state not in {ElectronicTaxDocument.State.DRAFT, ElectronicTaxDocument.State.READY}:
            raise ValidationError("Las lineas son inmutables desde FOLIO_RESERVED.")

    def save(self, *args, **kwargs):
        self._assert_editable()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._assert_editable()
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.document} - linea {self.line_number}"


class ElectronicTaxReference(models.Model):
    class Reason(models.TextChoices):
        CANCEL_DOCUMENT = "CANCEL_DOCUMENT", "Anular documento"
        CORRECT_TEXT = "CORRECT_TEXT", "Corregir texto"
        CANCEL_DEBIT_NOTE = "CANCEL_DEBIT_NOTE", "Anular nota de debito"
        CANCEL_CREDIT_NOTE = "CANCEL_CREDIT_NOTE", "Anular nota de credito"
        CORRECT_AMOUNTS = "CORRECT_AMOUNTS", "Corregir montos"

    document = models.ForeignKey(
        ElectronicTaxDocument,
        on_delete=models.PROTECT,
        related_name="references",
    )
    referenced_document = models.ForeignKey(
        ElectronicTaxDocument,
        on_delete=models.PROTECT,
        related_name="referenced_by",
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    reference_code = models.PositiveSmallIntegerField(default=1)
    reference_date = models.DateField()
    referenced_type_code = models.PositiveSmallIntegerField()
    referenced_folio = models.PositiveBigIntegerField()
    description = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "referenced_document", "reason"],
                name="uniq_dte_reference_reason",
            )
        ]

    def clean(self):
        super().clean()
        if self.document_id and self.referenced_document_id:
            if self.document.company_id != self.referenced_document.company_id:
                raise ValidationError({"referenced_document": "La referencia debe pertenecer a la misma empresa."})
            if self.document_id == self.referenced_document_id:
                raise ValidationError({"referenced_document": "Un DTE no puede referenciarse a si mismo."})

    def save(self, *args, **kwargs):
        if self.document.state not in {ElectronicTaxDocument.State.DRAFT, ElectronicTaxDocument.State.READY}:
            raise ValidationError("Las referencias son inmutables desde FOLIO_RESERVED.")
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.document.state not in {ElectronicTaxDocument.State.DRAFT, ElectronicTaxDocument.State.READY}:
            raise ValidationError("Las referencias son inmutables desde FOLIO_RESERVED.")
        return super().delete(*args, **kwargs)


class FolioReservation(models.Model):
    class Status(models.TextChoices):
        RESERVED = "RESERVED", "Reservado"
        CONSUMED = "CONSUMED", "Consumido"
        VOIDED = "VOIDED", "Anulado"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="folio_reservations",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="folio_reservations",
    )
    authorization = models.ForeignKey(
        FolioAuthorization,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    document = models.OneToOneField(
        ElectronicTaxDocument,
        on_delete=models.PROTECT,
        related_name="folio_reservation",
    )
    type_code = models.PositiveSmallIntegerField()
    folio = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RESERVED)
    reserved_at = models.DateTimeField(auto_now_add=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["company_id", "type_code", "folio"]
        constraints = [
            models.UniqueConstraint(fields=["company", "type_code", "folio"], name="uniq_folio_reservation_number")
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.company_id and self.branch_id and self.branch.company_id != self.company_id:
            errors["branch"] = "La sucursal debe pertenecer a la empresa del folio."
        if self.document_id:
            if self.document.company_id != self.company_id:
                errors["document"] = "El DTE debe pertenecer a la empresa del folio."
            if self.document.type_code != self.type_code:
                errors["type_code"] = "El tipo del folio debe coincidir con el DTE."
        if self.authorization_id:
            if self.authorization.company_id != self.company_id or self.authorization.type_code != self.type_code:
                errors["authorization"] = "La autorizacion no corresponde a la empresa/tipo del DTE."
            if not (self.authorization.start_folio <= self.folio <= self.authorization.end_folio):
                errors["folio"] = "El folio queda fuera del rango autorizado."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ElectronicTaxEvent(models.Model):
    class EventType(models.TextChoices):
        DRAFT_CREATED = "DRAFT_CREATED", "Borrador creado"
        VALIDATED = "VALIDATED", "Validado"
        DISCARDED = "DISCARDED", "Descartado"
        VERSION_CONFLICT = "VERSION_CONFLICT", "Conflicto de version"
        FOLIO_RESERVED = "FOLIO_RESERVED", "Folio reservado"
        FOLIO_CONSUMED = "FOLIO_CONSUMED", "Folio consumido"
        FOLIO_VOID_REQUESTED = "FOLIO_VOID_REQUESTED", "Anulacion tecnica solicitada"
        SIGNED = "SIGNED", "Firmado"
        SUBMIT_REQUESTED = "SUBMIT_REQUESTED", "Envio solicitado"
        SUBMITTED = "SUBMITTED", "Enviado"
        SEND_UNCERTAIN = "SEND_UNCERTAIN", "Envio incierto"
        STATUS_REFRESHED = "STATUS_REFRESHED", "Estado actualizado"
        ACCEPTED = "ACCEPTED", "Aceptado"
        ACCEPTED_WITH_REPAIR = "ACCEPTED_WITH_REPAIR", "Aceptado con reparo"
        REJECTED = "REJECTED", "Rechazado"
        CANCELLED_BY_REFERENCE = "CANCELLED_BY_REFERENCE", "Anulado por referencia"
        ACCESS_DENIED = "ACCESS_DENIED", "Acceso denegado"
        CROSS_TENANT_BLOCKED = "CROSS_TENANT_BLOCKED", "Acceso cruzado bloqueado"
        SECRET_OPERATION = "SECRET_OPERATION", "Operacion sensible"
        CREDIT_NOTE_CREATED = "CREDIT_NOTE_CREATED", "Nota de credito creada"
        DEBIT_NOTE_CREATED = "DEBIT_NOTE_CREATED", "Nota de debito creada"
        RIDE_GENERATED = "RIDE_GENERATED", "RIDE generado"
        RECEIVER_EXCHANGE_SENT = "RECEIVER_EXCHANGE_SENT", "DTE enviado al receptor"
        RECEIVER_EXCHANGE_UNCERTAIN = "RECEIVER_EXCHANGE_UNCERTAIN", "Envio al receptor incierto"
        RECEIVER_RESPONSE_RECEIVED = "RECEIVER_RESPONSE_RECEIVED", "Respuesta del receptor recibida"

    document = models.ForeignKey(
        ElectronicTaxDocument,
        on_delete=models.PROTECT,
        related_name="events",
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="electronic_tax_events")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="electronic_tax_events")
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="electronic_tax_events",
    )
    correlation_id = models.UUIDField(default=uuid.uuid4)
    normalized_code = models.CharField(max_length=80, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "created_at", "id"]

    def clean(self):
        super().clean()
        if self.document_id:
            if self.company_id != self.document.company_id or self.branch_id != self.document.branch_id:
                raise ValidationError("Empresa y sucursal del evento deben coincidir con el DTE.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class IdempotencyRecord(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="electronic_tax_idempotency_records",
    )
    operation = models.CharField(max_length=60)
    key = models.CharField(max_length=100)
    request_hash = models.CharField(max_length=64)
    document = models.ForeignKey(
        ElectronicTaxDocument,
        on_delete=models.PROTECT,
        related_name="idempotency_records",
        null=True,
        blank=True,
    )
    response_status = models.PositiveSmallIntegerField(default=200)
    response_body = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["company_id", "operation", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "operation", "key"], name="uniq_dte_idempotency_scope")
        ]

    def __str__(self):
        return f"{self.company_id}:{self.operation}:{self.key}"


class FolioAuthorizationSecret(models.Model):
    authorization = models.OneToOneField(
        FolioAuthorization, on_delete=models.CASCADE, related_name="secret_material"
    )
    nonce = models.BinaryField()
    encrypted_caf = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ElectronicTaxArtifact(models.Model):
    class Kind(models.TextChoices):
        SIGNED_ENVELOPE = "SIGNED_ENVELOPE", "EnvioDTE firmado"
        RIDE_PDF = "RIDE_PDF", "Representacion impresa PDF"
        RECEIVER_ENVELOPE = "RECEIVER_ENVELOPE", "EnvioDTE para receptor"
        RECEIVER_RESPONSE = "RECEIVER_RESPONSE", "Respuesta XML del receptor"

    document = models.ForeignKey(
        ElectronicTaxDocument, on_delete=models.PROTECT, related_name="artifacts"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    content_hash = models.CharField(max_length=64)
    nonce = models.BinaryField()
    encrypted_payload = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "kind"], name="uniq_dte_artifact_kind")
        ]


class FolioAuthorizationEvent(models.Model):
    class EventType(models.TextChoices):
        CAF_IMPORTED = "CAF_IMPORTED", "CAF importado"
        CAF_DISABLED = "CAF_DISABLED", "CAF deshabilitado"

    authorization = models.ForeignKey(
        FolioAuthorization, on_delete=models.PROTECT, related_name="audit_events"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="folio_authorization_events")
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    correlation_id = models.UUIDField(default=uuid.uuid4)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["authorization_id", "created_at", "id"]


class ElectronicTaxExchange(models.Model):
    class DeliveryState(models.TextChoices):
        NONE = "NONE", "Sin envio"
        PENDING = "PENDING", "Preparando envio"
        SENT = "SENT", "Enviado"
        SEND_UNCERTAIN = "SEND_UNCERTAIN", "Envio incierto"

    class ReceiverResponseState(models.TextChoices):
        NONE = "NONE", "Sin respuesta"
        RECEIVED = "RECEIVED", "Respuesta recibida"
        ACCEPTED = "ACCEPTED", "Aceptado"
        ACCEPTED_WITH_DISCREPANCY = "ACCEPTED_WITH_DISCREPANCY", "Aceptado con discrepancia"
        REJECTED = "REJECTED", "Rechazado"

    document = models.OneToOneField(
        ElectronicTaxDocument, on_delete=models.PROTECT, related_name="exchange"
    )
    delivery_state = models.CharField(
        max_length=24, choices=DeliveryState.choices, default=DeliveryState.NONE
    )
    recipient_email = models.EmailField(blank=True, default="")
    envelope_hash = models.CharField(max_length=64, blank=True, default="")
    ride_hash = models.CharField(max_length=64, blank=True, default="")
    send_attempts = models.PositiveIntegerField(default=0)
    last_send_error = models.CharField(max_length=500, blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    receiver_response_state = models.CharField(
        max_length=32,
        choices=ReceiverResponseState.choices,
        default=ReceiverResponseState.NONE,
    )
    receiver_response_code = models.CharField(max_length=40, blank=True, default="")
    receiver_response_message = models.CharField(max_length=500, blank=True, default="")
    receiver_response_hash = models.CharField(max_length=64, blank=True, default="")
    receiver_response_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.document_id and self.recipient_email:
            if self.recipient_email.strip().lower() != self.document.receiver_tax_email.strip().lower():
                raise ValidationError(
                    {"recipient_email": "El intercambio solo puede usar el correo tributario congelado del receptor."}
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ElectronicTaxOperationalAlert(models.Model):
    class Severity(models.TextChoices):
        INFO = "INFO", "Informacion"
        WARNING = "WARNING", "Advertencia"
        CRITICAL = "CRITICAL", "Critico"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Abierta"
        RESOLVED = "RESOLVED", "Resuelta"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="electronic_tax_operational_alerts",
    )
    code = models.CharField(max_length=64)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    dedupe_key = models.CharField(max_length=160)
    resource_kind = models.CharField(max_length=40, blank=True, default="")
    resource_id = models.CharField(max_length=64, blank=True, default="")
    message = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["company_id", "-severity", "code", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "dedupe_key"],
                name="uniq_dte_operational_alert_dedupe",
            )
        ]

    def __str__(self):
        return f"{self.company_id}:{self.code}:{self.status}"


class ElectronicTaxStatusCheckTask(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        RUNNING = "RUNNING", "Ejecutando"
        SUCCEEDED = "SUCCEEDED", "Completada"
        FAILED = "FAILED", "Fallida"
        CANCELLED = "CANCELLED", "Cancelada"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="electronic_tax_status_check_tasks",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="electronic_tax_status_check_tasks",
    )
    document = models.ForeignKey(
        ElectronicTaxDocument,
        on_delete=models.PROTECT,
        related_name="status_check_tasks",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="electronic_tax_status_check_tasks",
    )
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    reason = models.CharField(max_length=80)
    due_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=8)
    last_error = models.CharField(max_length=500, blank=True, default="")
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["state", "due_at"], name="dte_status_task_due_idx"),
            models.Index(fields=["company", "state"], name="dte_status_task_cmp_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.document_id:
            if self.document.company_id != self.company_id:
                errors["company"] = "La tarea debe pertenecer a la empresa del DTE."
            if self.document.branch_id != self.branch_id:
                errors["branch"] = "La tarea debe pertenecer a la sucursal del DTE."
        if self.max_attempts < 1:
            errors["max_attempts"] = "max_attempts debe ser al menos 1."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DTE {self.document_id} status-check {self.state}"
