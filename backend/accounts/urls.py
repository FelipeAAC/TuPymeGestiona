from django.urls import path

from accounts import views


urlpatterns = [
    path("csrf/", views.csrf_cookie, name="auth-csrf"),
    path("login/", views.login_view, name="auth-login"),
    path("me/", views.me_view, name="auth-me"),
    path("logout/", views.logout_view, name="auth-logout"),
    path(
        "password-reset/request/",
        views.password_reset_request_view,
        name="auth-password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        views.password_reset_confirm_view,
        name="auth-password-reset-confirm",
    ),
]
