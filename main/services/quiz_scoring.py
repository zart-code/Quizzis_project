from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Результат проверки одного вопроса."""

    points: int
    max_points: int
    is_correct: bool | None


class BaseScoringStrategy:
    """Базовая стратегия подсчета баллов."""

    @staticmethod
    def get_max_points(question) -> int:
        if question.question_type == "text":
            return 0
        return 4 * question.coefficient

    def score(self, question, submitted_value) -> ScoreResult:
        raise NotImplementedError


class SingleChoiceScoringStrategy(BaseScoringStrategy):
    """Стратегия для одиночного выбора."""

    def score(self, question, submitted_value) -> ScoreResult:
        max_points = self.get_max_points(question)
        correct_answer = next(
            (answer for answer in question.answers.all() if answer.is_correct),
            None,
        )

        if correct_answer and str(correct_answer.id) == submitted_value:
            return ScoreResult(
                points=max_points,
                max_points=max_points,
                is_correct=True,
            )

        return ScoreResult(
            points=0,
            max_points=max_points,
            is_correct=False,
        )


class MultipleChoiceScoringStrategy(BaseScoringStrategy):
    """Стратегия для множественного выбора."""

    def score(self, question, submitted_value) -> ScoreResult:
        max_points = self.get_max_points(question)
        chosen_ids = submitted_value or set()

        mistakes = 0
        for answer in question.answers.all():
            user_marked = str(answer.id) in chosen_ids
            if user_marked != answer.is_correct:
                mistakes += 1

        if mistakes == 0:
            points = max_points
        elif mistakes == 1:
            points = 2 * question.coefficient
        elif mistakes == 2:
            points = 1 * question.coefficient
        else:
            points = 0

        return ScoreResult(
            points=points,
            max_points=max_points,
            is_correct=(mistakes == 0),
        )


class NumberScoringStrategy(BaseScoringStrategy):
    """Стратегия для числового ответа."""

    def score(self, question, submitted_value) -> ScoreResult:
        max_points = self.get_max_points(question)

        try:
            is_correct = float(submitted_value) == question.correct_number
        except (TypeError, ValueError):
            is_correct = False

        return ScoreResult(
            points=max_points if is_correct else 0,
            max_points=max_points,
            is_correct=is_correct,
        )


class TextScoringStrategy(BaseScoringStrategy):
    """Стратегия для текстового ответа."""

    def score(self, question, submitted_value) -> ScoreResult:
        del question, submitted_value
        return ScoreResult(
            points=0,
            max_points=0,
            is_correct=None,
        )


class QuestionScoringFactory:
    """Фабрика стратегий подсчета баллов."""

    _strategies = {
        "single": SingleChoiceScoringStrategy(),
        "multiple": MultipleChoiceScoringStrategy(),
        "number": NumberScoringStrategy(),
        "text": TextScoringStrategy(),
    }

    @classmethod
    def get_strategy(cls, question_type):
        return cls._strategies.get(question_type, cls._strategies["text"])


def build_submission_value(request, question):
    """Достает из request пользовательский ответ в удобном виде."""
    if question.question_type == "single":
        return request.POST.get("answer")

    if question.question_type == "multiple":
        return set(request.POST.getlist("answer"))

    if question.question_type == "number":
        return request.POST.get("answer_number", "")

    if question.question_type == "text":
        return request.POST.get("answer_text", "")

    return None


def score_question(question, request, timed_out=False) -> ScoreResult:
    """Единая точка подсчета баллов по вопросу."""
    strategy = QuestionScoringFactory.get_strategy(question.question_type)
    max_points = strategy.get_max_points(question)

    if timed_out:
        is_correct = None if question.question_type == "text" else False
        return ScoreResult(
            points=0,
            max_points=max_points,
            is_correct=is_correct,
        )

    submitted_value = build_submission_value(request, question)
    return strategy.score(question, submitted_value)
