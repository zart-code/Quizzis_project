""" Service Layer """

from django.utils import timezone
from main.models import QuizRevision, RevisionQuestion, RevisionAnswer, Question


def calculate_revision_totals(question_payloads):
    question_count = len(question_payloads)
    max_score = 0

    for question in question_payloads:
        if question['question_type'] != Question.TEXT:
            max_score += 4 * question.get('coefficient', 1)

    return {
        'question_count': question_count,
        'max_score': max_score,
    }
