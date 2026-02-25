from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    """Кастомная форма регистрации."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

class StyledAuthenticationForm(AuthenticationForm):
    """Форма входа (без стилей)."""
    pass
