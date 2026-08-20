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
]
