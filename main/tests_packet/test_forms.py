from django.test import TestCase
from django.contrib.auth.models import User
from main.forms import CustomUserCreationForm, StyledAuthenticationForm
from main.models import Profile


class TestCustomUserCreationForm(TestCase):
    fixtures = ['db.json']

    def test_valid_student_registration(self):
        data = {
            'username': 'teststudent',
            'email': 'test@example.com',
            'password1': 'ComplexPass123',
            'password2': 'ComplexPass123',
            'role': Profile.STUDENT,
        }
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.profile.role, Profile.STUDENT)

    def test_valid_teacher_registration(self):
        data = {
            'username': 'testteacher',
            'email': 'teacher@example.com',
            'password1': 'ComplexPass123',
            'password2': 'ComplexPass123',
            'role': Profile.TEACHER,
        }
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.profile.role, Profile.TEACHER)


    def test_missing_role_field(self):
        data = {
            'username': 'testuser',
            'password1': 'ComplexPass123',
            'password2': 'ComplexPass123',
        }
        form = CustomUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('role', form.errors)

    def test_widget_attrs_have_form_control_class(self):
        form = CustomUserCreationForm()
        for field in form.fields.values():
            self.assertIn('class', field.widget.attrs)
            self.assertEqual(field.widget.attrs['class'], 'form-control')


class TestStyledAuthenticationForm(TestCase):
    def test_form_control_class_added(self):
        form = StyledAuthenticationForm()
        for field in form.fields.values():
            self.assertIn('class', field.widget.attrs)
            self.assertEqual(field.widget.attrs['class'], 'form-control')