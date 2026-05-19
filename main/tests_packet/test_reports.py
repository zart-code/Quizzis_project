"""Тесты жалоб на квизы"""

# pylint: disable=no-member,missing-class-docstring,missing-function-docstring

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from main.forms_features.forms_reports import QuizReportForm
from main.models import Profile, Quiz, QuizReport, QuizRevision


class QuizReportTests(TestCase):
    """Набор тестов для функционала жалоб на квизы: создание, дублирование, обработка администратором."""

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username="teacher",
            password="testpass123",
        )
        self.teacher.profile.role = Profile.TEACHER
        self.teacher.profile.save()

        self.student = User.objects.create_user(
            username="student",
            password="testpass123",
        )
        self.admin = User.objects.create_user(
            username="moderator",
            password="testpass123",
        )
        self.admin.profile.role = Profile.ADMIN
        self.admin.profile.is_admin = True
        self.admin.profile.save()

        self.quiz = Quiz.objects.create(
            title="History quiz",
            creator=self.teacher,
            status=Quiz.ACTIVE,
        )
        self.revision = QuizRevision.objects.create(
            quiz=self.quiz,
            version=1,
            title="History quiz",
        )
        self.quiz.current_revision = self.revision
        self.quiz.save(update_fields=["current_revision"])

    def test_other_reason_requires_comment(self):
        form = QuizReportForm(data={"reason": QuizReport.OTHER, "comment": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("comment", form.errors)

    def test_student_can_report_quiz(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("report_quiz", args=[self.quiz.id]),
            {
                "reason": QuizReport.WRONG_ANSWERS,
                "comment": "",
            },
        )

        self.assertRedirects(response, reverse("quizzes_view"))
        report = QuizReport.objects.get()
        self.assertEqual(report.quiz, self.quiz)
        self.assertEqual(report.revision, self.revision)
        self.assertEqual(report.reporter, self.student)
        self.assertEqual(report.status, QuizReport.PENDING)

    def test_duplicate_pending_report_is_not_created(self):
        """Повторная жалоба в статусе ожидания не создаётся."""
        self.client.force_login(self.student)
        url = reverse("report_quiz", args=[self.quiz.id])
        payload = {
            "reason": QuizReport.WRONG_ANSWERS,
            "comment": "",
        }

        self.client.post(url, payload)
        self.client.post(url, payload)

        self.assertEqual(QuizReport.objects.count(), 1)

    def test_creator_cannot_report_own_quiz(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("report_quiz", args=[self.quiz.id]),
            {
                "reason": QuizReport.WRONG_ANSWERS,
                "comment": "",
            },
        )

        self.assertRedirects(response, reverse("my_quizzes"))
        self.assertFalse(QuizReport.objects.exists())

    def test_admin_accept_report_returns_quiz_to_draft(self):
        report = QuizReport.objects.create(
            quiz=self.quiz,
            revision=self.revision,
            reporter=self.student,
            reason=QuizReport.WRONG_ANSWERS,
            comment="Wrong answer",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin_accept_report", args=[report.id]),
            {"admin_comment": "Исправьте правильный ответ."},
        )

        self.assertRedirects(response, reverse("admin_panel"))
        report.refresh_from_db()
        self.quiz.refresh_from_db()
        self.assertEqual(report.status, QuizReport.ACCEPTED)
        self.assertEqual(report.reviewed_by, self.admin)
        self.assertEqual(self.quiz.status, Quiz.DRAFT)

    def test_teacher_sees_accepted_report_feedback(self):
        QuizReport.objects.create(
            quiz=self.quiz,
            revision=self.revision,
            reporter=self.student,
            reason=QuizReport.WRONG_ANSWERS,
            comment="Wrong answer",
            status=QuizReport.ACCEPTED,
            admin_comment="Исправьте правильный ответ.",
            reviewed_by=self.admin,
        )
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("my_quizzes"))

        self.assertContains(response, "Нарушение подтверждено")
        self.assertContains(response, "Wrong answer")
        self.assertContains(response, "Исправьте правильный ответ.")
