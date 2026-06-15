"""
Сервис генерации квизов с помощью OpenRouter API (бесплатные модели).

Двухшаговая генерация:
1. generate_questions() — генерирует список вопросов (только тексты)
2. generate_quiz_from_questions() — по списку вопросов генерирует полный JSON с ответами
"""

import json
import logging
import urllib.request
import urllib.error

from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = getattr(settings, "OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "openai/gpt-4.1-nano"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
QUESTION_TYPES = ("single_choice", "multiple_choice", "number")
ALLOWED_TIME_LIMITS = (15, 20, 30, 45, 60)

QUESTION_TYPE_LABELS = {
    "single_choice": "один правильный ответ",
    "multiple_choice": "несколько правильных ответов",
    "number": "числовой ответ",
}
QUESTION_TYPE_COUNT_ALIASES = {
    "single_choice": ("single_choice", "single"),
    "multiple_choice": ("multiple_choice", "multiple"),
    "number": ("number",),
}

QUESTIONS_SYSTEM_PROMPT = """Ты — генератор вопросов для квизов. Твоя задача — придумать список вопросов по заданной теме.

Отвечай ТОЛЬКО валидным JSON. Никакого текста до или после. Никакой markdown-разметки.

Формат ответа:
{
  "title": "Название квиза",
  "questions": [
    "Текст первого вопроса?",
    "Текст второго вопроса?",
    "Текст третьего вопроса?"
  ]
}

Правила:
- Вопросы должны быть конкретными, фактически верными, проверяемыми и интересными.
- Разнообразь вопросы: факты, числа, сравнения, определения.
- Не повторяй один и тот же тип вопроса подряд.
- Формулируй коротко и чётко.
- НЕ придумывай факты. Все данные (числа, даты, названия, характеристики) должны быть правдивыми и проверяемыми.
- В вопросах не должно быть подсказок на ответ, если это не прописано дальше в запросе.
- Соблюдай план типов вопросов из пользовательского запроса.
- Для number формулируй вопрос так, чтобы правильный ответ был конкретным числом.
- Для multiple_choice формулируй вопрос так, чтобы у него было 2-3 правильных варианта.
"""

QUIZ_SYSTEM_PROMPT = """Ты — генератор квизов. Тебе даётся список вопросов. Для каждого вопроса создай полную структуру с ответами.

Правила:
1. type может быть: "single_choice" (один правильный), "multiple_choice" (несколько правильных), "number" (числовой ответ).
2. Для "single_choice" и "multiple_choice" — ровно 4 варианта в "options" с id: "A", "B", "C", "D".
3. Для "single_choice" — ровно 1 вариант с isCorrect: true.
4. Для "multiple_choice" — от 2 до 3 вариантов с isCorrect: true.
5. Для "number" — нет options, есть поле correctAnswer (число).
6. timeLimit: 15 сек, 20 сек, 30 сек, 45 сек, 60 сек
7. Сам оценивай сколько времени давать на ответ исходя из длины и сложности вопроса
8. id вопросов нумеруются с 1.
9. Используй type строго по плану типов из пользовательского запроса.
10. Сам оценивай сложность каждого вопроса и исходя из этого ставь коэфицент от 1 до 3
11. Для каждого вопроса выбирай уместные варианты ответов с учётом заданного type, сложности и темы.
12. В названии квиза нельзя писать "квиз" или "викторина" и так далее
13. Не выдумывай факты, вся информация должна быть достоверной
14. Научные факты важнее мифов. Даже если миф популярен
15. В multiple_choice ОБЯЗАТЕЛЬНО 2-3 правильных варианта ответа
16. НИКОГДА не оставляй во вариантах ответах пустые ячейки или надписи-заглушики, например "Варинат D"
17. В вопросах не должно быть подсказок на ответ, если это не прописано дальше в запросе
18. Не меняй вопросы которые в запросе: поле text должно дословно совпадать с переданным вопросом.
Формат:
{
  "title": "Название квиза",
  "questions": [
    {
      "id": 1,
      "type": "single_choice",
      "text": "Текст вопроса?",
      "coefficient": 1,
      "timeLimit": 30,
      "options": [
        {"id": "A", "text": "Вариант 1", "isCorrect": true},
        {"id": "B", "text": "Вариант 2", "isCorrect": false},
        {"id": "C", "text": "Вариант 3", "isCorrect": false},
        {"id": "D", "text": "Вариант 4", "isCorrect": false}
      ]
    },
    {
      "id": 2,
      "type": "number",
      "text": "Числовой вопрос?",
      "coefficient": 2,
      "timeLimit": 60,
      "correctAnswer": 42
    }
  ]
}"""


def _default_type_counts(num_questions: int) -> dict[str, int]:
    """Распределяет типы примерно поровну: 1/3 single, 1/3 multiple, 1/3 number."""
    base_count = num_questions // len(QUESTION_TYPES)
    remainder = num_questions % len(QUESTION_TYPES)

    counts = {q_type: base_count for q_type in QUESTION_TYPES}
    for q_type in QUESTION_TYPES[:remainder]:
        counts[q_type] += 1

    return counts


def _normalize_type_counts(
    num_questions: int,
    type_counts: dict | None = None,
) -> dict[str, int]:
    """Принимает будущие пользовательские настройки или возвращает дефолт 1/3."""
    if not isinstance(type_counts, dict):
        return _default_type_counts(num_questions)

    counts = {}
    for q_type in QUESTION_TYPES:
        raw_count = 0
        for alias in QUESTION_TYPE_COUNT_ALIASES[q_type]:
            if alias in type_counts:
                raw_count = type_counts.get(alias)
                break
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 0
        counts[q_type] = max(0, count)

    if sum(counts.values()) != num_questions:
        return _default_type_counts(num_questions)

    return counts


def _build_question_type_plan(
    num_questions: int,
    type_counts: dict | None = None,
) -> list[str]:
    """Создаёт упорядоченный план типов, чередуя их для более ровного квиза."""
    counts = _normalize_type_counts(num_questions, type_counts)
    remaining = counts.copy()
    plan = []

    while len(plan) < num_questions:
        added_in_round = False
        for q_type in QUESTION_TYPES:
            if remaining[q_type] > 0:
                plan.append(q_type)
                remaining[q_type] -= 1
                added_in_round = True
                if len(plan) == num_questions:
                    break
        if not added_in_round:
            break

    return plan


def _format_type_plan(type_plan: list[str]) -> str:
    lines = []
    for index, q_type in enumerate(type_plan, start=1):
        label = QUESTION_TYPE_LABELS[q_type]
        lines.append(f"{index}. {q_type} — {label}")
    return "\n".join(lines)


def _count_type_plan(type_plan: list[str]) -> dict[str, int]:
    return {q_type: type_plan.count(q_type) for q_type in QUESTION_TYPES}


def _call_openrouter(system_prompt: str, user_prompt: str) -> dict:
    """Вызов OpenRouter API (OpenAI-совместимый формат)."""
    api_key = OPENROUTER_API_KEY
    if not api_key:
        return {
            "success": False,
            "data": None,
            "error": "API ключ OpenRouter не настроен. Добавьте OPENROUTER_API_KEY в settings.py",
        }

    payload = json.dumps(
        {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    logger.info("Отправка запроса к OpenRouter: model=%s", OPENROUTER_MODEL)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        logger.error("OpenRouter HTTP %d: %s. Body: %s", e.code, e.reason, body)

        if e.code == 429:
            return {
                "success": False,
                "data": None,
                "error": "Превышен лимит запросов. Попробуйте позже.",
            }

        return {
            "success": False,
            "data": None,
            "error": f"OpenRouter вернул ошибку HTTP {e.code}: {e.reason}",
        }
    except urllib.error.URLError as e:
        logger.error("Не удалось подключиться к OpenRouter: %s", e)
        return {
            "success": False,
            "data": None,
            "error": "Не удалось подключиться к OpenRouter. Проверьте интернет.",
        }
    except Exception as e:
        logger.error("Ошибка при генерации: %s", e)
        return {"success": False, "data": None, "error": str(e)}

    # Извлекаем текст ответа (OpenAI-формат)
    try:
        raw_content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        logger.error("Неожиданный ответ OpenRouter: %s", json.dumps(result)[:500])
        return {
            "success": False,
            "data": None,
            "error": "OpenRouter вернул неожиданный формат ответа.",
        }

    parsed = _parse_json(raw_content)

    if parsed is None:
        logger.error("Невалидный JSON от OpenRouter: %s", raw_content[:500])
        return {
            "success": False,
            "data": None,
            "error": "Модель вернула невалидный JSON. Попробуйте ещё раз.",
        }

    return {"success": True, "data": parsed, "error": None}


def generate_questions(
    topic: str,
    num_questions: int = 5,
    difficulty: str = "medium",
    type_counts: dict | None = None,
) -> dict:
    """Шаг 1: Генерирует список вопросов (только тексты)."""
    difficulty_map = {
        "easy": "лёгкая (простые факты)",
        "medium": "средняя (требует размышления)",
        "hard": "сложная (глубокие знания)",
    }
    difficulty_desc = difficulty_map.get(difficulty, difficulty_map["medium"])
    type_plan = _build_question_type_plan(num_questions, type_counts)
    type_plan_text = _format_type_plan(type_plan)

    user_prompt = (
        f"Придумай {num_questions} вопросов для квиза на тему: «{topic}».\n"
        f"Сложность: {difficulty_desc}.\n"
        f"План типов вопросов по номерам:\n{type_plan_text}\n"
        f"Соблюдай этот план при формулировке вопросов.\n"
        f"Для number нужен вопрос с числовым ответом.\n"
        f"Для multiple_choice нужен вопрос, где реально есть 2-3 правильных варианта.\n"
        f"Отвечай ТОЛЬКО JSON."
    )

    result = _call_openrouter(QUESTIONS_SYSTEM_PROMPT, user_prompt)

    if not result["success"]:
        return result

    data = result["data"]
    title = data.get("title", topic) or topic
    questions_raw = data.get("questions", [])

    questions = []
    for q in questions_raw:
        if isinstance(q, str):
            questions.append(q.strip())
        elif isinstance(q, dict):
            questions.append(str(q.get("text", q.get("question", ""))).strip())

    questions = [q for q in questions if q]

    if not questions:
        return {
            "success": False,
            "data": None,
            "error": "Модель не сгенерировала ни одного вопроса.",
        }

    if len(questions) < num_questions:
        return {
            "success": False,
            "data": None,
            "error": "Модель сгенерировала меньше вопросов, чем было запрошено. Попробуйте ещё раз.",
        }

    questions = questions[:num_questions]
    type_plan = type_plan[:num_questions]

    return {
        "success": True,
        "data": {
            "title": title,
            "questions": questions,
            "typePlan": type_plan,
            "typeCounts": _count_type_plan(type_plan),
        },
        "error": None,
    }


def generate_quiz_from_questions(
    title: str,
    questions: list[str],
    type_counts: dict | None = None,
) -> dict:
    """Шаг 2: По списку вопросов генерирует полный JSON квиза с ответами."""
    questions_list = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, start=1))
    type_plan = _build_question_type_plan(len(questions), type_counts)
    type_plan_text = _format_type_plan(type_plan)

    user_prompt = (
        f"Название квиза: «{title}»\n\n"
        f"Вот список вопросов. Для каждого создай полную структуру с вариантами ответов:\n\n"
        f"{questions_list}\n\n"
        f"План типов вопросов по номерам:\n{type_plan_text}\n"
        f"Не выбирай тип самостоятельно, используй type из плана для каждого номера.\n"
        f"Не забывай, что у multiple_choice обязательно 2-3 правильных ответа.\n"
        f"Отвечай ТОЛЬКО JSON."
    )

    result = _call_openrouter(QUIZ_SYSTEM_PROMPT, user_prompt)

    if not result["success"]:
        return result

    validated = _validate_and_normalize(result["data"], title, questions, type_plan)
    return validated


def _parse_json(raw: str) -> dict | None:
    """Извлекает JSON из ответа модели."""
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _validate_and_normalize(
    quiz_data: dict,
    fallback_title: str,
    expected_questions: list[str] | None = None,
    type_plan: list[str] | None = None,
) -> dict:
    """Валидирует и нормализует JSON квиза под нужный формат."""
    title = quiz_data.get("title", fallback_title) or fallback_title
    questions_raw = quiz_data.get("questions", [])

    if not questions_raw:
        return {
            "success": False,
            "data": None,
            "error": "Модель не сгенерировала ни одного вопроса.",
        }

    expected_count = len(expected_questions) if expected_questions is not None else None
    if expected_count is not None and len(questions_raw) < expected_count:
        return {
            "success": False,
            "data": None,
            "error": "Модель сгенерировала меньше вопросов, чем было запрошено. Попробуйте ещё раз.",
        }

    if expected_count is not None:
        questions_raw = questions_raw[:expected_count]

    questions = []
    for i, q in enumerate(questions_raw, start=1):
        if type_plan and i <= len(type_plan):
            q_type = type_plan[i - 1]
        else:
            q_type = q.get("type", "single_choice")
        if q_type not in ("single_choice", "multiple_choice", "number"):
            q_type = "single_choice"

        time_limit = q.get("timeLimit", 30)
        if not isinstance(time_limit, int):
            time_limit = 30
        time_limit = min(ALLOWED_TIME_LIMITS, key=lambda allowed: abs(allowed - time_limit))

        coefficient = q.get("coefficient", 1)
        if not isinstance(coefficient, int) or coefficient < 1:
            coefficient = 1
        if coefficient > 3:
            coefficient = 3

        if expected_questions and i <= len(expected_questions):
            text = expected_questions[i - 1]
        else:
            text = str(q.get("text", f"Вопрос {i}"))

        question = {
            "id": i,
            "type": q_type,
            "text": text,
            "coefficient": coefficient,
            "timeLimit": time_limit,
        }

        if q_type in ("single_choice", "multiple_choice"):
            options = []
            option_ids = ["A", "B", "C", "D"]
            raw_options = q.get("options", [])

            for j, opt_id in enumerate(option_ids):
                if j < len(raw_options):
                    opt = raw_options[j]
                    options.append(
                        {
                            "id": opt_id,
                            "text": str(opt.get("text", f"Вариант {opt_id}")),
                            "isCorrect": bool(opt.get("isCorrect", False)),
                        }
                    )
                else:
                    options.append(
                        {
                            "id": opt_id,
                            "text": f"Вариант {opt_id}",
                            "isCorrect": False,
                        }
                    )

            if not any(o["isCorrect"] for o in options):
                options[0]["isCorrect"] = True

            correct_indexes = [
                idx for idx, option in enumerate(options) if option["isCorrect"]
            ]
            if q_type == "single_choice":
                first_correct = correct_indexes[0] if correct_indexes else 0
                for idx, option in enumerate(options):
                    option["isCorrect"] = idx == first_correct
            elif q_type == "multiple_choice":
                if len(correct_indexes) < 2:
                    correct_indexes = list(dict.fromkeys(correct_indexes + [0, 1]))[:2]
                elif len(correct_indexes) > 3:
                    correct_indexes = correct_indexes[:3]
                for idx, option in enumerate(options):
                    option["isCorrect"] = idx in correct_indexes

            question["options"] = options

        elif q_type == "number":
            correct = q.get("correctAnswer", 0)
            try:
                correct = float(correct)
                if correct == int(correct):
                    correct = int(correct)
            except (TypeError, ValueError):
                correct = 0
            question["correctAnswer"] = correct

        questions.append(question)

    result_data = {"title": title, "questions": questions}
    if type_plan:
        result_data["typePlan"] = type_plan
        result_data["typeCounts"] = _count_type_plan(type_plan)

    return {"success": True, "data": result_data, "error": None}
