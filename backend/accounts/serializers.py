from rest_framework import serializers

from accounts.models import User


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


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
        )
