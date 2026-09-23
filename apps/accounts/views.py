from django.contrib.auth.views import LoginView
from .forms import AccesoForm


class AccesoView(LoginView):
    authentication_form = AccesoForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(60 * 60 * 24 * 14 if form.cleaned_data.get("recordarme") else 0)
        return response
