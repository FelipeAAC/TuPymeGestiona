from django.core.exceptions import ValidationError
from django.db import models

from organizations.models import Company


class Category(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="categories",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["company_id", "name"]

    def clean(self):
        super().clean()

        if not self.parent_id:
            return

        if self.parent.company_id != self.company_id:
            raise ValidationError(
                {
                    "parent": (
                        "La categoria padre debe pertenecer "
                        "a la misma empresa."
                    )
                }
            )

        ancestor = self.parent
        visited = set()

        while ancestor is not None:
            if self.pk and ancestor.pk == self.pk:
                raise ValidationError(
                    {
                        "parent": (
                            "La jerarquia de categorias "
                            "no puede contener ciclos."
                        )
                    }
                )

            if ancestor.pk in visited:
                raise ValidationError(
                    {
                        "parent": (
                            "La jerarquia de categorias "
                            "no puede contener ciclos."
                        )
                    }
                )

            if ancestor.pk is not None:
                visited.add(ancestor.pk)

            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company} - {self.name}"


class Brand(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="brands",
    )
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["company_id", "name"]

    def __str__(self):
        return f"{self.company} - {self.name}"


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    class Meta:
        ordering = ["company_id", "name"]

    def clean(self):
        super().clean()

        if (
            self.category_id
            and self.company_id
            and self.category.company_id != self.company_id
        ):
            raise ValidationError(
                {
                    "category": (
                        "La categoria debe pertenecer "
                        "a la misma empresa que el producto."
                    )
                }
            )

        if (
            self.brand_id
            and self.company_id
            and self.brand.company_id != self.company_id
        ):
            raise ValidationError(
                {
                    "brand": (
                        "La marca debe pertenecer "
                        "a la misma empresa que el producto."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company} - {self.name}"


class ProductVariant(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="variants",
    )
    sku = models.CharField(max_length=100)
    gtin = models.CharField(
        max_length=32,
        blank=True,
    )
    base_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    class Meta:
        ordering = ["product_id", "sku"]

    def clean(self):
        super().clean()

        if self.product_id and self.sku:
            variants = ProductVariant.objects.filter(
                product__company_id=self.product.company_id,
                sku=self.sku,
            )

            if self.pk:
                variants = variants.exclude(pk=self.pk)

            if variants.exists():
                raise ValidationError(
                    {
                        "sku": (
                            "El SKU debe ser unico "
                            "dentro de la empresa."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} - {self.sku}"


class Supplier(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="suppliers",
    )
    name = models.CharField(max_length=200)
    contact_name = models.CharField(
        max_length=150,
        blank=True,
    )
    email = models.EmailField(
        blank=True,
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "name"]

    def __str__(self):
        return f"{self.company} - {self.name}"
