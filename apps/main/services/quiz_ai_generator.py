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
<<<<<<< HEAD
- В вопросах не должно быть подсказок на ответ, если это не прописано дальше в запросе.
=======
- Треть вопросов должна быть числовыми, треть одиночными, треть множественными
>>>>>>> 71b702b (новые правила)
"""

QUIZ_SYSTEM_PROMPT = """Ты — генератор квизов. Тебе даётся список вопросов. Для каждого вопроса создай полную структуру с ответами.

Правила:
1. type может быть: "single_choice" (один правильный), "multiple_choice" (несколько правильных), "number" (числовой ответ).
2. Для "single_choice" и "multiple_choice" — ровно 4 варианта в "options" с id: "A", "B", "C", "D".
3. Для "single_choice" — ровно 1 вариант с isCorrect: true.
4. Для "multiple_choice" — от 1 до 3 вариантов с isCorrect: true.
5. Для "number" — нет options, есть поле correctAnswer (число).
6. timeLimit: 15 сек, 20 сек, 30 сек, 45 сек, 60 сек
7. Сам оценивай сколько времени давать на ответ исходя из длины и сложности вопроса
8. id вопросов нумеруются с 1.
9. Выбирай тип вопроса исходя из формулировки: если ответ — число, используй "number"; если можно выбрать несколько, используй "multiple_choice"; иначе "single_choice".
10. Сам оценивай сложность каждого вопроса и исходя из этого ставь коэфицент от 1 до 3
11. Каждый раз думай какой лучше взять тип type вопроса, оценивай количество каждого типа вопроса в квизе в общем, сложность квиза, уместность
12. В названии квиза нельзя писать "квиз" или "викторина" и так далее
13. Не выдумывай факты, вся информация должна быть достоверной
14. Научные факты важнее мифов. Даже если миф популярен
<<<<<<< HEAD
15. В multiple_choice ОБЯЗАТЕЛЬНО минимум 1 правильный вариант ответа
16. НИКОГДА не оставляй во вариантах ответах пустые ячейки или надписи-заглушики, например "Варинат D"
17. В вопросах не должно быть подсказок на ответ, если это не прописано дальше в запросе
18. Не меняй вопросы которые в запросе
19. Треть вопросов должна быть числовыми, треть одиночными, треть множественными
=======

>>>>>>> 71b702b (новые правила)
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
) -> dict:
    """Шаг 1: Генерирует список вопросов (только тексты)."""
    difficulty_map = {
        "easy": "лёгкая (простые факты)",
        "medium": "средняя (требует размышления)",
        "hard": "сложная (глубокие знания)",
    }
    difficulty_desc = difficulty_map.get(difficulty, difficulty_map["medium"])

    user_prompt = (
        f"Придумай {num_questions} вопросов для квиза на тему: «{topic}».\n"
        f"Сложность: {difficulty_desc}.\n"
        f"Разнообразь типы: факты, числа, выбор из нескольких.\n"
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

    return {
        "success": True,
        "data": {"title": title, "questions": questions},
        "error": None,
    }


def generate_quiz_from_questions(
    title: str,
    questions: list[str],
) -> dict:
    """Шаг 2: По списку вопросов генерирует полный JSON квиза с ответами."""
    questions_list = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, start=1))

    user_prompt = (
        f"Название квиза: «{title}»\n\n"
        f"Вот список вопросов. Для каждого создай полную структуру с вариантами ответов:\n\n"
        f"{questions_list}\n\n"
        f"Используй разные типы: single_choice, multiple_choice, number.\n"
        f"Не забывай что у multiple_choice обязательно 2-3 правильных ответа.\n"
        f"Отвечай ТОЛЬКО JSON."
    )

    result = _call_openrouter(QUIZ_SYSTEM_PROMPT, user_prompt)

    if not result["success"]:
        return result

    validated = _validate_and_normalize(result["data"], title)
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


def _validate_and_normalize(quiz_data: dict, fallback_title: str) -> dict:
    """Валидирует и нормализует JSON квиза под нужный формат."""
    title = quiz_data.get("title", fallback_title) or fallback_title
    questions_raw = quiz_data.get("questions", [])

    if not questions_raw:
        return {
            "success": False,
            "data": None,
            "error": "Модель не сгенерировала ни одного вопроса.",
        }

    questions = []
    for i, q in enumerate(questions_raw, start=1):
        q_type = q.get("type", "single_choice")
        if q_type not in ("single_choice", "multiple_choice", "number"):
            q_type = "single_choice"

        time_limit = q.get("timeLimit", 30)
        if not isinstance(time_limit, int) or time_limit < 10:
            time_limit = 30
        if time_limit > 120:
            time_limit = 120

        coefficient = q.get("coefficient", 1)
        if not isinstance(coefficient, int) or coefficient < 1:
            coefficient = 1
        if coefficient > 3:
            coefficient = 3

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

    return {"success": True, "data": result_data, "error": None}
