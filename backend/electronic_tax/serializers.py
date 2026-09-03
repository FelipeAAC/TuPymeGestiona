from rest_framework import serializers

from .models import (
    ElectronicTaxDocument,
    ElectronicTaxEvent,
    ElectronicTaxLine,
    ElectronicTaxReference,
    ElectronicTaxExchange,
)


class ElectronicTaxLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectronicTaxLine
        fields = (
            "id",
            "line_number",
            "variant",
            "sku",
            "description",
            "quantity",
            "unit_price",
            "discount_amount",
            "tax_category",
            "net_amount",
            "exempt_amount",
            "vat_amount",
            "total_amount",
        )
        read_only_fields = fields


class ElectronicTaxReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectronicTaxReference
        fields = (
            "id",
            "referenced_document",
            "reason",
            "reference_code",
            "reference_date",
            "referenced_type_code",
            "referenced_folio",
            "description",
            "created_at",
        )
        read_only_fields = fields


class ElectronicTaxEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectronicTaxEvent
        fields = (
            "id",
            "event_type",
            "actor",
            "correlation_id",
            "normalized_code",
            "metadata",
            "created_at",
        )
        read_only_fields = fields




class ElectronicTaxExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectronicTaxExchange
        fields = (
            "delivery_state",
            "recipient_email",
            "envelope_hash",
            "ride_hash",
            "send_attempts",
            "last_send_error",
            "sent_at",
            "receiver_response_state",
            "receiver_response_code",
            "receiver_response_message",
            "receiver_response_hash",
            "receiver_response_at",
        )
        read_only_fields = fields


class ElectronicTaxDocumentSerializer(serializers.ModelSerializer):
    lines = ElectronicTaxLineSerializer(many=True, read_only=True)
    references = ElectronicTaxReferenceSerializer(many=True, read_only=True)
    events = ElectronicTaxEventSerializer(many=True, read_only=True)
    exchange = ElectronicTaxExchangeSerializer(read_only=True)

    class Meta:
        model = ElectronicTaxDocument
        fields = (
            "id",
            "company",
            "branch",
            "sale",
            "type_code",
            "state",
            "version",
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
            "issue_date",
            "folio",
            "provider_track_id",
            "provider_status_code",
            "provider_status_message",
            "provider_last_checked_at",
            "snapshot_hash",
            "xml_hash",
            "correlation_id",
            "created_by",
            "created_at",
            "updated_at",
            "discarded_at",
            "lines",
            "references",
            "events",
            "exchange",
        )
        read_only_fields = fields


class ElectronicTaxDocumentCreateSerializer(serializers.Serializer):
    sale_id = serializers.IntegerField(min_value=1)
    type_code = serializers.ChoiceField(
        choices=(
            ElectronicTaxDocument.TypeCode.INVOICE,
            ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE,
        )
    )


class ElectronicTaxMutationSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)


class ElectronicTaxNoteCreateSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=ElectronicTaxReference.Reason.choices)
    description = serializers.CharField(max_length=250, allow_blank=False, trim_whitespace=True)
    correction = serializers.DictField(
        child=serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True),
        required=False,
        default=dict,
    )


class ElectronicTaxListQuerySerializer(serializers.Serializer):
    branch = serializers.IntegerField(min_value=1, required=False)
    type_code = serializers.ChoiceField(choices=ElectronicTaxDocument.TypeCode.choices, required=False)
    state = serializers.ChoiceField(choices=ElectronicTaxDocument.State.choices, required=False)
    folio = serializers.IntegerField(min_value=1, required=False)
    receiver_rut = serializers.CharField(max_length=20, required=False, allow_blank=False)
    issue_date_from = serializers.DateField(required=False)
    issue_date_to = serializers.DateField(required=False)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)

    def validate(self, attrs):
        start = attrs.get("issue_date_from")
        end = attrs.get("issue_date_to")
        if start and end and start > end:
            raise serializers.ValidationError("issue_date_from no puede ser posterior a issue_date_to.")
        return attrs
