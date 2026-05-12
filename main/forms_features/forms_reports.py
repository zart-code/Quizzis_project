from django import forms

from main.models import QuizReport


class QuizReportForm(forms.ModelForm):
    """Форма отправки жалобы на квиз."""

    class Meta:
        model = QuizReport
        fields = ["reason", "comment"]
        widgets = {
            "reason": forms.Select(attrs={"class": "form-control"}),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Опишите проблему, если нужно.",
                }
            ),
        }
        labels = {
            "reason": "Причина",
            "comment": "Комментарий",
        }

    def clean(self):
        cleaned_data = super().clean()
        reason = cleaned_data.get("reason")
        comment = cleaned_data.get("comment", "").strip()

        if reason == QuizReport.OTHER and not comment:
            self.add_error(
                "comment",
                "Для причины «Другое» нужно описать проблему.",
            )

        cleaned_data["comment"] = comment
        return cleaned_data