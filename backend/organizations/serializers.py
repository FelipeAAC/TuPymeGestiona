from rest_framework import serializers

from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    Permission,
    RoleAssignment,
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
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = CompanyMembership
        fields = (
            "id",
            "status",
            "company",
            "branches",
            "permissions",
        )

    def get_branches(self, membership):
        has_company_admin = membership.role_assignments.filter(
            role__status="ACTIVE",
            branch__isnull=True,
            role__permission_links__permission__code="administration.manage",
        ).exists()
        if has_company_admin:
            branches = membership.company.branches.filter(is_active=True).order_by("name")
        else:
            branch_ids = set(
                membership.branch_memberships.filter(
                    branch__is_active=True,
                ).values_list("branch_id", flat=True)
            )
            branch_ids.update(
                membership.role_assignments.filter(
                    role__status="ACTIVE",
                    branch__isnull=False,
                    role__permission_links__permission__scope_behavior=(
                        Permission.ScopeBehavior.BRANCH_SCOPED
                    ),
                ).values_list("branch_id", flat=True)
            )
            branches = membership.company.branches.filter(
                is_active=True,
                id__in=branch_ids,
            ).order_by("name")
        return BranchSerializer(branches, many=True).data

    def get_permissions(self, membership):
        if getattr(membership.user, "is_superuser", False):
            from organizations.models import Permission

            return list(Permission.objects.order_by("code").values_list("code", flat=True))

        return list(
            RoleAssignment.objects.filter(
                membership=membership,
                role__status="ACTIVE",
            )
            .values_list("role__permission_links__permission__code", flat=True)
            .exclude(role__permission_links__permission__code__isnull=True)
            .order_by("role__permission_links__permission__code")
            .distinct()
        )


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "id",
            "company",
            "branch",
            "code",
            "name",
            "is_active",
        )


class WarehouseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "company",
            "branch",
            "code",
            "name",
            "is_active",
        )
        extra_kwargs = {"is_active": {"required": False}}

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
            "is_active",
        )
        extra_kwargs = {"is_active": {"required": False}}

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
