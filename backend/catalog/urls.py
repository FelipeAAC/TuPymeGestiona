from django.urls import path

from catalog import views


urlpatterns = [
    path(
        "products/",
        views.product_list_view,
        name="catalog-product-list",
    ),
    path(
        "products/<int:product_id>/",
        views.product_detail_view,
        name="catalog-product-detail",
    ),
    path(
        "products/<int:product_id>/variants/",
        views.product_variant_create_view,
        name="catalog-product-variant-create",
    ),
    path(
        "products/<int:product_id>/variants/<int:variant_id>/",
        views.product_variant_detail_view,
        name="catalog-product-variant-detail",
    ),
    path(
        "products/options/",
        views.product_options_view,
        name="catalog-product-options",
    ),
    path(
        "categories/",
        views.category_list_create_view,
        name="catalog-category-list-create",
    ),
    path(
        "brands/",
        views.brand_list_create_view,
        name="catalog-brand-list-create",
    ),
    path(
        "suppliers/",
        views.supplier_list_create_view,
        name="catalog-supplier-list-create",
    ),
]
