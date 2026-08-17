from rest_framework import serializers

from organizations.models import Branch, Company, CompanyMembership


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
