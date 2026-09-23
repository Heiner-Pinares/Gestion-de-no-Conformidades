from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import AccesoView
urlpatterns = [path("login/", AccesoView.as_view(), name="login"), path("logout/", LogoutView.as_view(), name="logout")]
