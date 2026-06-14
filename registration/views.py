from django.shortcuts import render

from main.forms import CustomUserCreationForm
from main.views import _handle_form


# Create your views here.
def register_page(request):
    """Страница регистрации"""
    return _handle_form(
        request,
        form_class=CustomUserCreationForm,
        template_name="register.html",
        success_url="main_page",
    )
