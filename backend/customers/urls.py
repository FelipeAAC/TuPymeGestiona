from django.urls import path

from . import views


urlpatterns = [
    path("",views.customer_list_create_view,name="customer-list-create",
    ),
]
