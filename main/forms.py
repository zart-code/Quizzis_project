# main/forms.py
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    """
    Кастомная форма регистрации. При необходимости можно добавить поля,
    например email. Пока оставим стандартные (username, password1, password2)
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields  # ('username',)