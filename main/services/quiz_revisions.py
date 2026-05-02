from django.db import transaction
from django.db.models import Max
from main.models import (
    Question,
    QuizRevision,
    RevisionAnswer,
    RevisionQuestion,
)


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


def collect_question_payloads_from_post(request):
    """Собирает вопросы из POST в нормализованный список словарей."""
    question_indexes = []

    for key, value in request.POST.items():
        if not key.endswith('_text'):
            continue

        prefix, _, suffix = key.partition('_')
        if suffix != 'text':
            continue

        if prefix.startswith('q') and value.strip():
            try:
                question_indexes.append(int(prefix[1:]))
            except ValueError:
                continue

    question_indexes.sort()

    question_payloads = []
    for order, index in enumerate(question_indexes, start=1):
        question_type = request.POST.get(f'q{index}_type', 'single')
        time_limit = int(request.POST.get(f'q{index}_time', 30))
        coefficient = int(request.POST.get(f'q{index}_coefficient', 1) or 1)

        payload = {
            'text': request.POST.get(f'q{index}_text', '').strip(),
            'question_type': question_type,
            'time_limit': time_limit,
            'coefficient': coefficient,
            'order': order,
            'correct_number': None,
            'answers': [],
        }

        if question_type == 'single':
            correct_index = request.POST.get(f'q{index}_correct')
            for answer_index in range(4):
                payload['answers'].append({
                    'text': request.POST.get(f'q{index}_ans{answer_index}', '').strip(),
                    'is_correct': str(answer_index) == correct_index,
                    'order': answer_index + 1,
                })

        elif question_type == 'multiple':
            correct_indexes = set(request.POST.getlist(f'q{index}_correct'))
            for answer_index in range(4):
                payload['answers'].append({
                    'text': request.POST.get(f'q{index}_ans{answer_index}', '').strip(),
                    'is_correct': str(answer_index) in correct_indexes,
                    'order': answer_index + 1,
                })

        elif question_type == 'number':
            raw_number = request.POST.get(f'q{index}_correct_number', '0')
            try:
                payload['correct_number'] = float(raw_number)
            except ValueError:
                payload['correct_number'] = 0

        question_payloads.append(payload)

    return question_payloads


def calculate_revision_totals(question_payloads):
    """Считает количество вопросов и максимальный балл ревизии."""
    question_count = len(question_payloads)
    max_score = 0

    for question_payload in question_payloads:
        if question_payload['question_type'] != Question.TEXT:
            max_score += 4 * question_payload['coefficient']

    return {
        'question_count': question_count,
        'max_score': max_score,
    }


@transaction.atomic
def create_revision_from_payloads(quiz, title, question_payloads):
    """Создает новую ревизию квиза и делает ее текущей."""
    revision_totals = calculate_revision_totals(question_payloads)
    last_version = quiz.revisions.aggregate(
        last_version=Max('version'),
    )['last_version'] or 0
    next_version = last_version + 1

    revision = QuizRevision.objects.create(
        quiz=quiz,
        version=next_version,
        title=title,
        question_count=revision_totals['question_count'],
        max_score=revision_totals['max_score'],
    )

    for question_payload in question_payloads:
        revision_question = RevisionQuestion.objects.create(
            revision=revision,
            text=question_payload['text'],
            question_type=question_payload['question_type'],
            correct_number=question_payload['correct_number'],
            coefficient=question_payload['coefficient'],
            time_limit=question_payload['time_limit'],
            order=question_payload['order'],
        )

        for answer_payload in question_payload['answers']:
            RevisionAnswer.objects.create(
                question=revision_question,
                text=answer_payload['text'],
                is_correct=answer_payload['is_correct'],
                order=answer_payload['order'],
            )

    quiz.current_revision = revision
    quiz.save(update_fields=['current_revision'])

    return revision

