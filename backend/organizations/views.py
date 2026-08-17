from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import CompanyMembership
from organizations.serializers import OrganizationContextMembershipSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def organization_context_view(request):
    memberships = (
        CompanyMembership.objects.filter(
            user=request.user,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .prefetch_related("branch_memberships__branch")
    )

    return Response(
        {
            "memberships": OrganizationContextMembershipSerializer(
                memberships,
                many=True,
            ).data,
        }
    )
