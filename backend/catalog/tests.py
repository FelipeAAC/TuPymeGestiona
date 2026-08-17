from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import Company

from .models import Brand, Category, Product, ProductVariant


class CatalogModelsTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Empresa Catalog A",
        )
        self.company_b = Company.objects.create(
            name="Empresa Catalog B",
        )

        self.category_a = Category.objects.create(
            company=self.company_a,
            name="Categoria A",
        )
        self.category_b = Category.objects.create(
            company=self.company_b,
            name="Categoria B",
        )

        self.brand_a = Brand.objects.create(
            company=self.company_a,
            name="Marca A",
        )
        self.brand_b = Brand.objects.create(
            company=self.company_b,
            name="Marca B",
        )

    def test_category_can_be_root(self):
        self.assertIsNone(self.category_a.parent)

    def test_category_can_have_parent_from_same_company(self):
        child = Category.objects.create(
            company=self.company_a,
            parent=self.category_a,
            name="Subcategoria A",
        )

        self.assertEqual(child.parent, self.category_a)

    def test_category_parent_must_belong_to_same_company(self):
        with self.assertRaises(ValidationError):
            Category.objects.create(
                company=self.company_a,
                parent=self.category_b,
                name="Subcategoria Invalida",
            )

    def test_category_cannot_be_its_own_parent(self):
        category = Category.objects.create(
            company=self.company_a,
            name="Categoria Self",
        )

        category.parent = category

        with self.assertRaises(ValidationError):
            category.save()

    def test_category_hierarchy_cannot_contain_indirect_cycle(self):
        parent = Category.objects.create(
            company=self.company_a,
            name="Categoria Parent",
        )

        child = Category.objects.create(
            company=self.company_a,
            parent=parent,
            name="Categoria Child",
        )

        parent.parent = child

        with self.assertRaises(ValidationError):
            parent.save()

    def test_product_category_must_belong_to_same_company(self):
        with self.assertRaises(ValidationError):
            Product.objects.create(
                company=self.company_a,
                category=self.category_b,
                name="Producto Categoria Invalida",
            )

    def test_product_can_exist_without_brand(self):
        product = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto Sin Marca",
        )

        self.assertIsNone(product.brand)

    def test_product_brand_must_belong_to_same_company(self):
        with self.assertRaises(ValidationError):
            Product.objects.create(
                company=self.company_a,
                category=self.category_a,
                brand=self.brand_b,
                name="Producto Marca Invalida",
            )

    def test_product_defaults_to_draft(self):
        product = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            brand=self.brand_a,
            name="Producto Draft",
        )

        self.assertEqual(
            product.status,
            Product.Status.DRAFT,
        )

    def test_product_variant_defaults_to_draft(self):
        product = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto Variante",
        )

        variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-001",
            base_price=Decimal("12990.00"),
        )

        self.assertEqual(
            variant.status,
            ProductVariant.Status.DRAFT,
        )
        self.assertEqual(
            variant.base_price,
            Decimal("12990.00"),
        )

    def test_sku_must_be_unique_inside_company(self):
        product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto A1",
        )
        product_a_2 = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto A2",
        )

        ProductVariant.objects.create(
            product=product_a,
            sku="SKU-SHARED",
            base_price=Decimal("1000.00"),
        )

        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(
                product=product_a_2,
                sku="SKU-SHARED",
                base_price=Decimal("2000.00"),
            )

    def test_same_sku_can_exist_in_different_companies(self):
        product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto Empresa A",
        )
        product_b = Product.objects.create(
            company=self.company_b,
            category=self.category_b,
            name="Producto Empresa B",
        )

        variant_a = ProductVariant.objects.create(
            product=product_a,
            sku="SKU-COMPARTIDO",
            base_price=Decimal("1000.00"),
        )
        variant_b = ProductVariant.objects.create(
            product=product_b,
            sku="SKU-COMPARTIDO",
            base_price=Decimal("2000.00"),
        )

        self.assertEqual(
            variant_a.sku,
            variant_b.sku,
        )
