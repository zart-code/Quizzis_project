from main.models import Question


def get_current_revision(quiz):
    """Возвращает текущую ревизию квиза, если она есть."""
    return quiz.current_revision


def get_revision_questions(revision):
    """Возвращает вопросы ревизии с ответами."""
    if revision is None:
        return []

    return list(
        revision.questions.prefetch_related('answers').order_by('order', 'id')
    )


def get_quiz_questions(quiz):
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


def get_quiz_question_count(quiz):
    """Количество вопросов в текущей версии квиза."""
    revision = get_current_revision(quiz)
    if revision is not None:
        return revision.question_count

    return quiz.questions.count()


def get_quiz_max_score(quiz):
    """Максимальный балл в текущей версии квиза."""
    revision = get_current_revision(quiz)
    if revision is not None:
        return revision.max_score

    total = 0
    for question in quiz.questions.all():
        if question.question_type != Question.TEXT:
            total += 4 * question.coefficient
    return total


def get_session_questions(session):
    """Возвращает вопросы игровой сессии."""
    if session.revision_id:
        return list(
            session.revision.questions.prefetch_related('answers').order_by('order', 'id')
        )

    return list(
        session.quiz.questions.prefetch_related('answers').order_by('order', 'id')
    )


def get_session_max_score(session):
    """Возвращает максимальный балл игровой сессии."""
    if session.revision_id:
        return session.revision.max_score

    return get_quiz_max_score(session.quiz)


def get_revision_question_count_for_result(result):
    """Количество вопросов для конкретного результата."""
    if result.revision_id:
        return result.revision.question_count

    return result.quiz.total_questions()


def build_revision_payload(revision):
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
