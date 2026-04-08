"""Формы для views"""
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

FIELD_ATTRS = {'class': 'form-control'}


class CustomUserCreationForm(UserCreationForm):
    """Форма пользователя"""
    class Meta(UserCreationForm.Meta):
        """Метаданные"""
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(FIELD_ATTRS)


class StyledAuthenticationForm(AuthenticationForm):
    """Стилистическая форма"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(FIELD_ATTRS)

