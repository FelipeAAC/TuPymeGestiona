from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from accounts.models import User
from accounts.access import get_access_context


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        max_length=254,
        trim_whitespace=True,
    )
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    remember_me = serializers.BooleanField(
        required=False,
        default=False,
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254, trim_whitespace=True)

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128, trim_whitespace=True)
    token = serializers.CharField(max_length=256, trim_whitespace=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        invalid = {"detail": "El enlace de recuperación no es válido o expiró."}
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
        except (TypeError, ValueError, OverflowError):
            raise serializers.ValidationError(invalid)

        user = User.objects.filter(pk=user_id, is_active=True).first()
        if user is None or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(invalid)

        try:
            password_validation.validate_password(attrs["password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        attrs["user"] = user
        return attrs


class CurrentUserSerializer(serializers.ModelSerializer):
    access_modes = serializers.SerializerMethodField()
    default_app = serializers.SerializerMethodField()
    managed_companies = serializers.SerializerMethodField()
    portal_companies = serializers.SerializerMethodField()

    def _access_context(self, user):
        # A ListSerializer reuses its child serializer for every object. Resolve
        # from the object passed to each method rather than caching one user's
        # context on the shared serializer instance.
        return get_access_context(user)

    def get_access_modes(self, user):
        return self._access_context(user)["access_modes"]

    def get_default_app(self, user):
        return self._access_context(user)["default_app"]

    def get_managed_companies(self, user):
        return self._access_context(user)["managed_companies"]

    def get_portal_companies(self, user):
        return self._access_context(user)["portal_companies"]

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "access_modes",
            "default_app",
            "managed_companies",
            "portal_companies",
        )
