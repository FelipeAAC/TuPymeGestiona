from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Identidad global de usuario en TuPymeGestiona.

    La pertenencia a empresas, sucursales, roles y permisos
    se gestiona mediante los módulos organizacionales/RBAC,
    no directamente en este modelo.
    """

    email = models.EmailField(
        "email address",
        unique=True,
    )
