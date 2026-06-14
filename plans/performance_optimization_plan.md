# План оптимизации производительности: замена polling на WebSocket

## Текущая ситуация

Проект использует **HTTP polling** для real-time обновлений в игровых сессиях:

### Точки polling:
1. **lobby.html** (игрок в лобби):
   - `api_state` - проверка статуса игры (1 сек)
   - `api_check_kicked` - проверка кика (1 сек)

2. **session_play.html** (игрок во время игры):
   - `get_current_question` - проверка смены вопроса (1 сек)

3. **lobby.html** (хост во время игры):
   - `api_players` - список игроков (1 сек)
   - `api_game_stats` - статистика игры (1 сек)

### Проблема:
- При 1000 игроков = **4000+ HTTP запросов/сек**
- Каждый запрос = overhead (headers, TCP handshake, DB query)
- Задержка до 1 секунды между событиями
- Неэффективное использование ресурсов сервера

---

## Решение: Django Channels + Redis + WebSocket

### Почему этот стек?

✅ **Django Channels** - официальный Django-пакет для WebSocket, async, long-polling  
✅ **Используется миллионами** (Discord, Twitch, Slack используют подобные решения)  
✅ **Нативная интеграция с Django** (ORM, auth, sessions)  
✅ **Redis** - стандартный message broker (используется везде)  
✅ **Готовое решение** для real-time (не нужно изобретать велосипед)

---

## Архитектура

### До (текущая):
```
[Browser] --HTTP GET (polling 1s)--> [Django View] --> [Database]
[Browser] --HTTP GET (polling 1s)--> [Django View] --> [Database]
[Browser] --HTTP GET (polling 1s)--> [Django View] --> [Database]
... (тысячи запросов/сек)
```

### После (оптимизированная):
```
[Browser] <--WebSocket (persistent)--> [ASGI Server]
                                            ↓
                                    [Channel Layer]
                                            ↓
                                      [Redis Pub/Sub]
                                            ↓
                                    [Django Consumer]
                                            ↓
                                      [Database]
```

### Как это работает:
1. **WebSocket-соединение** устанавливается один раз при заходе в лобби
2. **События** (новый игрок, смена вопроса, ответ) публикуются в Redis
3. **Все подключенные клиенты** получают событие мгновенно через WebSocket
4. **Нет polling** - только push-уведомления при реальных изменениях

---

## План реализации

### Фаза 1: Установка и настройка инфраструктуры

#### 1.1. Установка зависимостей
```bash
pip install channels channels-redis daphne
```

#### 1.2. Обновление `settings.py`
```python
INSTALLED_APPS = [
    'daphne',  # ASGI server
    'channels',
    # ... остальные apps
]

# Channel layers (Redis для production, In-memory для тестов)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}

ASGI_APPLICATION = 'quizziz_project.asgi.application'
```

#### 1.3. Создание `asgi.py` (если нет)
```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quizziz_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            # Здесь будут WebSocket маршруты
        )
    ),
})
```

---

### Фаза 2: Создание WebSocket consumers

#### 2.1. Структура файлов
```
main/
├── consumers/
│   ├── __init__.py
│   ├── lobby_consumer.py      # Для лобби (игроки + хост)
│   └── game_consumer.py       # Для игровой сессии
└── routing.py                 # WebSocket URL-маршруты
```

#### 2.2. `lobby_consumer.py` - обработка лобби

**Группы (каналы):**
- `lobby_{pin}` - все участники лобби (игроки + хост)
- `lobby_host_{pin}` - только хост

**События:**
- `player_joined` - новый игрок присоединился
- `player_kicked` - игрок выгнан
- `lobby_locked` - лобби закрыто/открыто
- `game_started` - игра началась
- `question_advanced` - учитель переключил вопрос

```python
# Пример структуры consumer
class LobbyConsumer(WebsocketConsumer):
    def connect(self):
        self.pin = self.scope['url_route']['kwargs']['pin']
        self.lobby_group = f'lobby_{self.pin}'
        self.host_group = f'lobby_host_{self.pin}'
        
        # Добавляем в группы
        async_to_sync(self.channel_layer.group_add)(
            self.lobby_group, self.channel_name
        )
        
        # Если это хост - добавляем в группу хоста
        if self.scope['user'] == session.host:
            async_to_sync(self.channel_layer.group_add)(
                self.host_group, self.channel_name
            )
        
        self.accept()
    
    def disconnect(self, close_code):
        # Убираем из групп
        async_to_sync(self.channel_layer.group_discard)(
            self.lobby_group, self.channel_name
        )
    
    # Обработчики событий
    def player_joined(self, event):
        self.send(text_data=json.dumps({
            'type': 'player_joined',
            'player': event['player']
        }))
    
    def game_started(self, event):
        self.send(text_data=json.dumps({
            'type': 'game_started',
            'message': 'Игра началась!'
        }))
```

---

### Фаза 3: Обновление views для публикации событий

#### 3.1. Создание сервиса `main/services/websocket_events.py`

```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def broadcast_player_joined(pin, player_data):
    """Уведомить всех в лобби о новом игроке"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'lobby_{pin}',
        {
            'type': 'player_joined',
            'player': player_data
        }
    )

def broadcast_game_started(pin):
    """Уведомить всех о начале игры"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'lobby_{pin}',
        {
            'type': 'game_started',
            'message': 'Игра началась!'
        }
    )

def broadcast_question_advanced(pin, question_data):
    """Уведомить игроков о смене вопроса"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'game_{pin}',
        {
            'type': 'question_advanced',
            'question': question_data
        }
    )
```

#### 3.2. Обновление `views_lobby.py`

**Пример: `join_lobby_view`**

```python
from apps.main import broadcast_player_joined


def join_lobby_view(request, pin):
    # ... существующая логика ...

    participant, created = GameParticipant.objects.get_or_create(
        session=session, user=current_user
    )

    if created:
        # Публикуем событие через WebSocket
        broadcast_player_joined(pin, {
            'id': participant.id,
            'username': participant.get_display_name()
        })

    # ... остальная логика ...
```

**Пример: `start_game_view`**

```python
from apps.main import broadcast_game_started


def start_game_view(request, pin):
    # ... существующая логика ...

    session.status = GameSession.IN_PROGRESS
    session.save()

    # Уведомляем всех игроков
    broadcast_game_started(pin)

    return redirect('lobby', pin=pin)
```

**Пример: `advance_question_view`**

```python
from apps.main import broadcast_question_advanced


def advance_question_view(request, pin):
    # ... существующая логика ...

    session.current_question += 1
    session.save()

    # Уведомляем игроков о новом вопросе
    broadcast_question_advanced(pin, {
        'current_question': session.current_question,
        'status': session.status
    })

    return JsonResponse({'success': True})
```

---

### Фаза 4: Обновление frontend (JavaScript)

#### 4.1. Создание `main/static/js/websocket.js`

```javascript
class LobbyWebSocket {
    constructor(pin) {
        this.pin = pin;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.connect();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/lobby/${this.pin}/`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket подключен');
            this.reconnectAttempts = 0;
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket отключен');
            this.attemptReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket ошибка:', error);
        };
    }
    
    handleMessage(data) {
        switch(data.type) {
            case 'player_joined':
                this.onPlayerJoined(data.player);
                break;
            case 'player_kicked':
                this.onPlayerKicked(data.player_id);
                break;
            case 'game_started':
                this.onGameStarted();
                break;
            case 'question_advanced':
                this.onQuestionAdvanced(data.question);
                break;
        }
    }
    
    onPlayerJoined(player) {
        // Обновляем список игроков
        const list = document.getElementById('players-list');
        const chip = document.createElement('li');
        chip.className = 'player-chip';
        chip.dataset.id = player.id;
        chip.innerHTML = `
            <span class="player-chip-name">👤 ${escapeHtml(player.username)}</span>
            <button class="kick-btn" onclick="kickPlayer(${player.id}, '${escapeHtml(player.username)}')">✕ Выгнать</button>
        `;
        list.appendChild(chip);
        
        // Обновляем счетчик
        const count = document.getElementById('player-count');
        count.textContent = parseInt(count.textContent) + 1;
        
        // Активируем кнопку "Начать игру"
        document.getElementById('start-btn').disabled = false;
    }
    
    onGameStarted() {
        // Перенаправляем на страницу игры
        window.location.href = `/session/${this.pin}/play/`;
    }
    
    onQuestionAdvanced(questionData) {
        // Перезагружаем страницу для получения нового вопроса
        window.location.reload();
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            console.log(`Попытка переподключения через ${delay}мс...`);
            setTimeout(() => this.connect(), delay);
        }
    }
    
    close() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Экспорт
window.LobbyWebSocket = LobbyWebSocket;
```

#### 4.2. Обновление `lobby.html`

**Удалить:**
```javascript
// УДАЛИТЬ весь polling-код
setInterval(fetchPlayers, 1000);
setInterval(checkGameState, 1500);
```

**Добавить:**
```html
<script src="{% static 'js/websocket.js' %}"></script>
<script>
    const lobbyWs = new LobbyWebSocket("{{ session.pin }}");
    
    // Функции для обработки событий
    function kickPlayer(participantId, username) {
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const url = `/lobby/${pin}/api/kick/${participantId}/`;
        
        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken }
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                // Удаление произойдет автоматически через WebSocket
                console.log('Игрок выгнан');
            }
        });
    }
</script>
```

#### 4.3. Обновление `session_play.html`

**Удалить:**
```javascript
// УДАЛИТЬ polling
function checkForNextQuestion(){
    fetch(apiCurrentQuestionUrl)...
}
```

**Добавить:**
```javascript
const gameWs = new LobbyWebSocket("{{ session.pin }}");

// Автоматическая перезагрузка при смене вопроса
gameWs.onQuestionAdvanced = (data) => {
    if (data.current_question !== currentQuestion || data.status === 'finished') {
        window.location.reload();
    }
};
```

---

### Фаза 5: Опционально - Celery для фоновых задач

#### Зачем Celery?

✅ **Очистка гостевых пользователей** (сейчас синхронно в `advance_question_view`)  
✅ **Тяжелые вычисления** (статистика, аналитика)  
✅ **Email-уведомления** (если добавим)  
✅ **Отложенные задачи** (автоматическое завершение сессий через N часов)

#### 5.1. Установка
```bash
pip install celery redis
```

#### 5.2. Создание `quizziz_project/celery.py`
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quizziz_project.settings')

app = Celery('quizziz_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

#### 5.3. Создание задач `main/tasks.py`

```python
from celery import shared_task
from django.utils import timezone
from apps.main import GameSession, GameParticipant
from django.contrib.auth.models import User


@shared_task
def cleanup_guest_users_task(session_id):
    """Удаляет гостевых пользователей завершённой сессии"""
    try:
        session = GameSession.objects.get(id=session_id)
        guest_participants = session.participants.filter(
            user__username__startswith='guest_'
        ).select_related('user')

        deleted_count = 0
        for participant in guest_participants:
            guest_user = participant.user
            has_active = GameParticipant.objects.filter(
                user=guest_user,
                session__status__in=[GameSession.WAITING, GameSession.IN_PROGRESS]
            ).exclude(session=session).exists()

            if not has_active:
                guest_user.delete()
                deleted_count += 1

        return f'Удалено {deleted_count} гостевых пользователей'
    except GameSession.DoesNotExist:
        return 'Сессия не найдена'


@shared_task
def auto_finish_expired_sessions():
    """Автоматически завершает сессии старше 3 часов"""
    expired = GameSession.objects.filter(
        status=GameSession.IN_PROGRESS,
        created_at__lt=timezone.now() - timezone.timedelta(hours=3)
    )

    count = expired.update(status=GameSession.FINISHED)
    return f'Завершено {count} просроченных сессий'
```

#### 5.4. Обновление `settings.py`
```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Moscow'

# Периодические задачи
CELERY_BEAT_SCHEDULE = {
    'auto-finish-expired-sessions': {
        'task': 'main.tasks.auto_finish_expired_sessions',
        'schedule': 3600.0,  # Каждый час
    },
}
```

#### 5.5. Обновление views

```python
from apps.main import cleanup_guest_users_task


def advance_question_view(request, pin):
    # ... существующая логика ...

    if session.current_question >= total_questions:
        session.status = GameSession.FINISHED
        session.save()

        # Запускаем очистку в фоне
        cleanup_guest_users_task.delay(session.id)

    return JsonResponse({'success': True})
```

---

### Фаза 6: Production deployment

#### 6.1. Daphne (ASGI server для WebSocket)
```bash
daphne -b 0.0.0.0 -p 8000 quizziz_project.asgi:application
```

#### 6.2. Nginx конфигурация
```nginx
upstream channels_backend {
    server localhost:8000;
}

server {
    location /ws/ {
        proxy_pass http://channels_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        # Обычный HTTP трафик
        proxy_pass http://localhost:8001;  # Gunicorn
    }
}
```

#### 6.3. Systemd service для Daphne
```ini
[Unit]
Description=Daphne ASGI Server
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/daphne -b 0.0.0.0 -p 8000 quizziz_project.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 6.4. Systemd service для Celery worker
```ini
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/celery -A quizziz_project worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 6.5. Systemd service для Celery beat
```ini
[Unit]
Description=Celery Beat Scheduler
After=network.target redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/celery -A quizziz_project beat -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Оценка производительности

### До оптимизации (polling):
- **1000 игроков** × **4 запроса/сек** = **4000 HTTP запросов/сек**
- Нагрузка на CPU: высокая (обработка каждого запроса)
- Нагрузка на DB: высокая (каждый запрос = SELECT)
- Задержка: до 1 секунды

### После оптимизации (WebSocket):
- **1000 игроков** = **1000 WebSocket соединений** (persistent)
- События публикуются только при реальных изменениях
- Нагрузка на CPU: низкая (только push-уведомления)
- Нагрузка на DB: низкая (запросы только при действиях пользователей)
- Задержка: <100ms (мгновенно)

**Экономия ресурсов: ~90%**

---

## Риски и митигация

### Риск 1: WebSocket отключается
**Митигация:**
- Автоматическое переподключение (exponential backoff)
- Fallback на polling если WebSocket недоступен

### Риск 2: Redis падает
**Митигация:**
- Redis Sentinel для высокой доступности
- In-memory channel layer для разработки/тестов

### Риск 3: Daphne не справляется с нагрузкой
**Митигация:**
- Запуск нескольких экземпляров Daphne за load balancer'ом
- Использование Uvicorn (более производительный ASGI server)

---

## Чек-лист реализации

### Фаза 1: Инфраструктура
- [ ] Установить channels, channels-redis, daphne
- [ ] Обновить settings.py (CHANNEL_LAYERS, ASGI_APPLICATION)
- [ ] Создать/обновить asgi.py
- [ ] Установить и настроить Redis
- [ ] Протестировать базовое WebSocket соединение

### Фаза 2: Consumers
- [ ] Создать `main/consumers/lobby_consumer.py`
- [ ] Создать `main/consumers/game_consumer.py`
- [ ] Создать `main/routing.py` с WebSocket маршрутами
- [ ] Протестировать подключение к WebSocket

### Фаза 3: Backend события
- [ ] Создать `main/services/websocket_events.py`
- [ ] Обновить `join_lobby_view` (broadcast player_joined)
- [ ] Обновить `kick_player_view` (broadcast player_kicked)
- [ ] Обновить `start_game_view` (broadcast game_started)
- [ ] Обновить `advance_question_view` (broadcast question_advanced)
- [ ] Обновить `toggle_lock_view` (broadcast lobby_locked)

### Фаза 4: Frontend
- [ ] Создать `main/static/js/websocket.js`
- [ ] Обновить `lobby.html` (удалить polling, добавить WebSocket)
- [ ] Обновить `join_lobby.html` (удалить polling, добавить WebSocket)
- [ ] Обновить `session_play.html` (удалить polling, добавить WebSocket)
- [ ] Протестировать real-time обновления

### Фаза 5: Celery (опционально)
- [ ] Установить celery
- [ ] Создать `quizziz_project/celery.py`
- [ ] Создать `main/tasks.py`
- [ ] Обновить settings.py (CELERY_*)
- [ ] Обновить views для использования .delay()
- [ ] Настроить Celery Beat для периодических задач

### Фаза 6: Production
- [ ] Настроить Daphne (systemd service)
- [ ] Настроить Nginx (WebSocket proxy)
- [ ] Настроить Redis (systemd service)
- [ ] Настроить Celery worker (systemd service)
- [ ] Настроить Celery beat (systemd service)
- [ ] Настроить мониторинг (Prometheus + Grafana)
- [ ] Load testing (Locust/k6)

---

## Альтернативы (если не подходит)

### 1. Server-Sent Events (SSE)
**Плюсы:** проще WebSocket, работает через HTTP  
**Минусы:** однонаправленный (server → client), не подходит для двусторонней связи

### 2. Long Polling
**Плюсы:** работает везде, не требует WebSocket  
**Минусы:** всё ещё много HTTP запросов, сложнее в реализации

### 3. Firebase Realtime Database / Pusher
**Плюсы:** готовое решение, не нужно поддерживать инфраструктуру  
**Минусы:** платно, зависимость от внешнего сервиса, данные уходят на сторону

**Вывод:** Django Channels + Redis - оптимальный выбор для вашего случая.

---

## Полезные ссылки

- [Django Channels Documentation](https://channels.readthedocs.io/)
- [Channels Redis Documentation](https://github.com/django/channels_redis)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Daphne Documentation](https://github.com/django/daphne)
- [Redis Documentation](https://redis.io/documentation)

---

## Вопросы для обсуждения

1. **Нужен ли Celery?** Если только для очистки гостей - можно оставить синхронно. Если планируете email-уведомления, аналитику - однозначно нужен.

2. **Redis на том же сервере или отдельно?** Для начала - на том же. При росте нагрузки - вынести на отдельный сервер.

3. **Нужна ли поддержка offline-режима?** Если игрок потерял связь - переподключится автоматически. История событий не теряется (хранится в БД).

4. **Мониторинг?** Рекомендуется Prometheus + Grafana для отслеживания:
   - Количество активных WebSocket соединений
   - Latency сообщений
   - Нагрузка на Redis
   - Ошибки WebSocket

5. **Тестирование?** Написать unit-тесты для consumers и integration-тесты для WebSocket flow.
