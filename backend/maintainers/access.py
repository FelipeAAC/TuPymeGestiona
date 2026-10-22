from rest_framework.permissions import BasePermission

from accounts.access import is_platform_admin


class IsPlatformAdmin(BasePermission):
    """Allow only users with the explicit platform-admin capability."""

    message = "Solo un administrador de plataforma puede usar esta API."

    def has_permission(self, request, view):
        return is_platform_admin(request.user)
