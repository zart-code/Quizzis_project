"""Формы для views"""
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from main.models import Profile

FIELD_ATTRS = {'class': 'form-control'}


class CustomUserCreationForm(UserCreationForm):
    """Форма пользователя"""
    role = forms.ChoiceField(
        choices=[
            (Profile.TEACHER, 'Учитель'),
            (Profile.STUDENT, 'Ученик'),
        ],
        label='Роль',
    )

    class Meta(UserCreationForm.Meta):
        """Метаданные"""
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(FIELD_ATTRS)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and hasattr(user, 'profile'):
            if user.username == 'admin':
                user.profile.role = Profile.ADMIN
                user.profile.is_admin = True
            else:
                user.profile.role = self.cleaned_data['role']
                user.profile.is_admin = False
            user.profile.save()
        return user


class StyledAuthenticationForm(AuthenticationForm):
    """Стилистическая форма"""
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(FIELD_ATTRS)

