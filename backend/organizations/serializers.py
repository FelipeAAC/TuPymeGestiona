from rest_framework import serializers

from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    Warehouse,
)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "name",
        )


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = (
            "id",
            "code",
            "name",
        )


class OrganizationContextMembershipSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    branches = serializers.SerializerMethodField()

    class Meta:
        model = CompanyMembership
        fields = (
            "id",
            "status",
            "company",
            "branches",
        )

    def get_branches(self, membership):
        branches = [
            membership_branch.branch
            for membership_branch in membership.branch_memberships.all()
        ]

        return BranchSerializer(branches, many=True).data


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "id",
            "company",
            "branch",
            "code",
            "name",
        )


class WarehouseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "company",
            "branch",
            "code",
            "name",
        )

    def validate(self, attrs):
        company = self.context["company"]
        branch = attrs.get("branch")

        if branch is not None and branch.company_id != company.id:
            raise serializers.ValidationError(
                {
                    "branch": (
                        "La sucursal debe pertenecer a la misma empresa que la bodega."
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        return Warehouse.objects.create(
            **validated_data,
        )


class WarehouseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "branch",
            "code",
            "name",
        )

    def validate(self, attrs):
        company = self.context["company"]
        branch = attrs.get("branch")

        if branch is not None and branch.company_id != company.id:
            raise serializers.ValidationError(
                {
                    "branch": (
                        "La sucursal debe pertenecer a la misma empresa que la bodega."
                    )
                }
            )

        return attrs
