"""
Тесты для форм приложения main.
"""

from django.test import TestCase
from django.contrib.auth.models import (
    User,
)  # noqa: F401 (оставлен для возможного использования)
from main.forms import CustomUserCreationForm, StyledAuthenticationForm
from main.models import Profile


class TestCustomUserCreationForm(TestCase):
    """Тесты для формы регистрации CustomUserCreationForm."""

    fixtures = ["db.json"]

    def test_valid_student_registration(self):
        """
        Проверка: регистрация студента с корректными данными успешна,
        роль пользователя устанавливается в STUDENT.
        """
        data = {
            "username": "teststudent",
            "email": "test@example.com",
            "password1": "ComplexPass123",
            "password2": "ComplexPass123",
            "role": Profile.STUDENT,
        }
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.profile.role, Profile.STUDENT)

    def test_valid_teacher_registration(self):
        """
        Проверка: регистрация учителя с корректными данными успешна,
        роль пользователя устанавливается в TEACHER.
        """
        data = {
            "username": "testteacher",
            "email": "teacher@example.com",
            "password1": "ComplexPass123",
            "password2": "ComplexPass123",
            "role": Profile.TEACHER,
        }
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.profile.role, Profile.TEACHER)

    def test_missing_role_field(self):
        """
        Проверка: при отсутствии поля role форма не проходит валидацию
        и содержит ошибку для поля role.
        """
        data = {
            "username": "testuser",
            "password1": "ComplexPass123",
            "password2": "ComplexPass123",
        }
        form = CustomUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)

    def test_widget_attrs_have_form_control_class(self):
        """
        Проверка: все поля формы имеют CSS-класс 'form-control'.
        """
        form = CustomUserCreationForm()
        for field in form.fields.values():
            self.assertIn("class", field.widget.attrs)
            self.assertEqual(field.widget.attrs["class"], "form-control")


class TestStyledAuthenticationForm(TestCase):
    """Тесты для формы аутентификации StyledAuthenticationForm."""

    def test_form_control_class_added(self):
        """
        Проверка: все поля формы входа имеют CSS-класс 'form-control'.
        """
        form = StyledAuthenticationForm()
        for field in form.fields.values():
            self.assertIn("class", field.widget.attrs)
            self.assertEqual(field.widget.attrs["class"], "form-control")
