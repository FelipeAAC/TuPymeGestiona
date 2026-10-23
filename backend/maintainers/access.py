from rest_framework.permissions import BasePermission

from accounts.access import is_destructive_admin, is_platform_admin


class IsPlatformAdmin(BasePermission):
    """Allow only users with the explicit platform-admin capability."""

    message = "Solo un administrador de plataforma puede usar esta API."

    def has_permission(self, request, view):
        return is_platform_admin(request.user)


class IsDestructiveAdmin(BasePermission):
    """Allow permanent deletion only to the explicitly delegated account."""

    message = "Esta cuenta no tiene permiso para eliminar datos permanentemente."

    def has_permission(self, request, view):
        return is_destructive_admin(request.user)
