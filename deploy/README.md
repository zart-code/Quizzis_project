# Деплой Quizzis (WebSocket-архитектура)

Проект перешёл с HTTP-polling на real-time через **Django Channels +
Redis + Daphne (ASGI)**. Gunicorn (WSGI) больше не используется, так как
не умеет обслуживать WebSocket.

## Что нужно на сервере

1. **Redis** — брокер для channel layer:
   ```bash
   sudo apt-get install -y redis-server
   sudo systemctl enable --now redis-server
   redis-cli ping   # -> PONG
   ```

2. **Daphne** ставится из `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

3. **Systemd-сервис Daphne** — скопировать и поправить пути:
   ```bash
   sudo cp deploy/daphne-quizzis.service /etc/systemd/system/
   # отредактировать WorkingDirectory, ExecStart, пути к venv
   sudo systemctl daemon-reload
   sudo systemctl enable --now daphne-quizzis
   ```

4. **Nginx** — проксирование HTTP и `/ws/`:
   ```bash
   sudo cp deploy/nginx-quizzis.conf /etc/nginx/sites-available/quizzis
   sudo ln -s /etc/nginx/sites-available/quizzis /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `QUIZZIS_REDIS_URL` | URL Redis для channel layer | `redis://127.0.0.1:6379/0` |
| `QUIZZIS_INMEMORY_CHANNELS` | `1` — использовать in-memory слой (без Redis) | не задано |
| `DJANGO_DEBUG` | `True`/`False` | `False` |

## Локальная разработка

Запуск ASGI-сервера разработки (Daphne подключается автоматически как
`runserver` через `INSTALLED_APPS`):

```bash
python manage.py runserver
```

Нужен запущенный Redis. Если Redis нет — можно поднять без него:

```bash
QUIZZIS_INMEMORY_CHANNELS=1 python manage.py runserver
```

> ⚠️ In-memory слой работает только в рамках одного процесса и не годится
> для production (события не доставляются между воркерами).

## Тесты

Тесты автоматически используют in-memory channel layer (Redis не нужен):

```bash
python manage.py test
```
