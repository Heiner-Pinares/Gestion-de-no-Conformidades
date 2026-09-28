from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import AccesoView, microsoft_callback, microsoft_start

urlpatterns = [
    path("login/", AccesoView.as_view(), name="login"),
    path("microsoft/iniciar/", microsoft_start, name="microsoft_start"),
    path("microsoft/callback/", microsoft_callback, name="microsoft_callback"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
