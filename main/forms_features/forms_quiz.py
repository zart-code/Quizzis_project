from django import forms
from django.forms import inlineformset_factory

from main.models import Quiz, Question, Answer


class QuizForm(forms.ModelForm):
    """Форма создания/редактирования квиза."""

    creator_name = forms.CharField(
        max_length=150,
        label="Имя создателя",
        required=True,
        help_text="Отображаемое имя автора квиза",
    )

    class Meta:
        model = Quiz
        fields = [
            "title",
            "category",
            "description",
            "additional_info",
            "time_limit",
            "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "additional_info": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            full_name = self.user.get_full_name() or self.user.username
            self.fields["creator_name"].initial = full_name

    def save(self, commit=True):
        quiz = super().save(commit=False)
        if self.user:
            quiz.creator = self.user
        if commit:
            quiz.save()
        return quiz


class QuestionForm(forms.ModelForm):
    """Форма вопроса."""

    class Meta:
        model = Question
        fields = ["text", "question_type", "order"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 2}),
            "order": forms.HiddenInput(),
        }


class AnswerForm(forms.ModelForm):
    """Форма варианта ответа."""

    class Meta:
        model = Answer
        fields = ["text", "is_correct"]


# Formset для вариантов ответа внутри одного вопроса
AnswerFormSet = inlineformset_factory(
    Question,
    Answer,
    form=AnswerForm,
    extra=2,
    min_num=2,
    validate_min=True,
    can_delete=True,
)
