from django.urls import path

from catalog import views


urlpatterns = [
    path(
        "products/",
        views.product_list_view,
        name="catalog-product-list",
    ),
    path(
        "products/options/",
        views.product_options_view,
        name="catalog-product-options",
    ),
]
