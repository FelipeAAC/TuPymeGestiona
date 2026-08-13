from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Identidad global de usuario en TuPymeGestiona.

    La pertenencia a empresas, sucursales, roles y permisos
    se gestionará mediante los módulos organizacionales/RBAC,
    no directamente en este modelo.
    """

    pass
