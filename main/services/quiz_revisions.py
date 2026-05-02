from main.models import Quiz, QuizRevision, RevisionQuestion, RevisionAnswer, Question


def get_current_revision(quiz: Quiz):
    """Возвращает текущую ревизию квиза, если она есть."""
    return quiz.current_revision


def get_revision_questions(revision: QuizRevision):
    """Возвращает вопросы ревизии с ответами."""
    if revision is None:
        return []
    return list(
        revision.questions.prefetch_related('answers').order_by('order', 'id')
    )


def get_quiz_questions(quiz: Quiz):
    """
    Возвращает структуру вопросов квиза.
    Сначала пробует ревизии, если их нет — старые Question.
    """
    revision = get_current_revision(quiz)
    if revision is not None:
        return get_revision_questions(revision)

    return list(
        quiz.questions.prefetch_related('answers').order_by('order', 'id')
    )


def get_quiz_question_count(quiz: Quiz) -> int:
    """Количество вопросов в текущей версии квиза."""
    revision = get_current_revision(quiz)
    if revision is not None:
        return revision.question_count

    return quiz.questions.count()


def get_quiz_max_score(quiz: Quiz) -> int:
    """Максимальный балл в текущей версии квиза."""
    revision = get_current_revision(quiz)
    if revision is not None:
        return revision.max_score

    total = 0
    for question in quiz.questions.all():
        if question.question_type != Question.TEXT:
            total += 4 * question.coefficient
    return total


def build_revision_payload(revision: QuizRevision):
    """Готовит данные ревизии для формы редактирования."""
    if revision is None:
        return {
            'title': '',
            'questions': [],
        }

    return {
        'title': revision.title,
        'questions': [
            {
                'text': question.text,
                'type': question.question_type,
                'time': question.time_limit,
                'coefficient': question.coefficient,
                'correct_number': question.correct_number,
                'answers': [
                    {
                        'text': answer.text,
                        'is_correct': answer.is_correct,
                    }
                    for answer in question.answers.all().order_by('order', 'id')
                ],
            }
            for question in revision.questions.all().order_by('order', 'id')
        ],
    }


def get_revision_question_count_for_result(result) -> int:
    """
    Количество вопросов для конкретного результата.
    Берем из ревизии результата, а если ее нет — из текущего квиза.
    """
    if result.revision_id:
        return result.revision.question_count
    return result.quiz.total_questions()
