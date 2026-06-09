/**
 * WebSocket клиент для real-time обновлений в лобби и игровой сессии.
 *
 * Предоставляет два класса:
 * - LobbyWebSocket — для страницы лобби (игроки, кик, старт)
 * - GameWebSocket — для страницы игры (смена вопроса, завершение)
 *
 * Поддерживает автоматическое переподключение с exponential backoff.
 */

/**
 * Класс WebSocket-клиента для лобби.
 *
 * Обрабатывает события:
 * - player_joined — новый игрок присоединился
 * - player_kicked — игрок выгнан
 * - lobby_locked — лобби закрыто/открыто
 * - game_started — игра началась
 * - session_deleted — сессия удалена
 */
class LobbyWebSocket {
    /**
     * Создать WebSocket-соединение для лобби.
     * @param {string} pin — PIN-код игровой сессии
     */
    constructor(pin) {
        this.pin = pin;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.connect();
    }

    /**
     * Установить WebSocket-соединение с сервером.
     */
    connect() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/lobby/${this.pin}/`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log(`[WS] Lobby WebSocket подключен: pin=${this.pin}`);
            this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error("[WS] Ошибка парсинга JSON:", e);
            }
        };

        this.ws.onclose = (event) => {
            console.log(`[WS] Lobby WebSocket отключен: code=${event.code}`);
            if (event.code !== 1000) {
                this.attemptReconnect();
            }
        };

        this.ws.onerror = (error) => {
            console.error("[WS] Lobby WebSocket ошибка:", error);
        };
    }

    /**
     * Обработать входящее сообщение от сервера.
     * @param {Object} data — распарсенный JSON-объект сообщения
     */
    handleMessage(data) {
        switch (data.type) {
            case "player_joined":
                this.onPlayerJoined(data.player);
                break;
            case "player_kicked":
                this.onPlayerKicked(data.player_id, data.player_name);
                break;
            case "lobby_locked":
                this.onLobbyLocked(data.is_locked);
                break;
            case "game_started":
                this.onGameStarted(data.pin);
                break;
            case "session_deleted":
                this.onSessionDeleted(data.pin);
                break;
            default:
                console.log("[WS] Неизвестный тип сообщения:", data.type);
        }
    }

    /**
     * Обработать подключение нового игрока.
     * @param {Object} player — данные игрока {id, username}
     */
    onPlayerJoined(player) {
        const list = document.getElementById("players-list");
        if (!list) return;

        // Удалить сообщение «Ожидание игроков...», если оно есть
        const emptyItem = list.querySelector(".players-empty");
        if (emptyItem) {
            emptyItem.remove();
        }

        // Проверяем, не добавлен ли уже этот игрок
        const existing = list.querySelector(`[data-id="${player.id}"]`);
        if (existing) return;

        const chip = document.createElement("li");
        chip.className = "player-chip";
        chip.dataset.id = player.id;
        chip.innerHTML = `
            <span class="player-chip-name">👤 ${escapeHtml(player.username)}</span>
            <button class="kick-btn" onclick="kickPlayer(${player.id}, '${escapeHtml(player.username)}')">✕ Выгнать</button>
        `;
        list.appendChild(chip);

        // Обновить счётчик
        const countEl = document.getElementById("player-count");
        if (countEl) {
            const chips = list.querySelectorAll(".player-chip");
            countEl.textContent = chips.length;
        }

        // Активировать кнопку «Начать игру»
        const startBtn = document.getElementById("start-btn");
        if (startBtn) {
            startBtn.disabled = false;
        }
    }

    /**
     * Обработать исключение игрока из лобби.
     * @param {number} playerId — ID исключённого участника
     * @param {string} playerName — имя исключённого участника
     */
    onPlayerKicked(playerId, playerName) {
        // Проверяем, не выгнали ли нас самих
        const storedId = window.storedParticipantId;
        if (storedId && String(storedId) === String(playerId)) {
            window.location.href = "/?kicked=1";
            return;
        }

        const chip = document.querySelector(`.player-chip[data-id="${playerId}"]`);
        if (chip) {
            chip.remove();
        }

        const list = document.getElementById("players-list");
        if (list) {
            const chips = list.querySelectorAll(".player-chip");
            const countEl = document.getElementById("player-count");
            if (countEl) {
                countEl.textContent = chips.length;
            }

            if (chips.length === 0) {
                list.innerHTML = '<li class="players-empty">Ожидание игроков...</li>';
                const startBtn = document.getElementById("start-btn");
                if (startBtn) {
                    startBtn.disabled = true;
                }
            }
        }
    }

    /**
     * Обработать изменение статуса закрытия лобби.
     * @param {boolean} isLocked — True если лобби закрыто
     */
    onLobbyLocked(isLocked) {
        const badge = document.getElementById("lock-status-badge");
        if (badge) {
            badge.innerHTML = isLocked
                ? '<span class="lbadge lbadge-danger">Закрыто</span>'
                : '<span class="lbadge lbadge-success">Открыто</span>';
        }
    }

    /**
     * Обработать начало игры — перенаправить на страницу игры.
     * @param {string} pin — PIN-код сессии
     */
    onGameStarted(pin) {
        console.log(`[WS] Игра началась: pin=${pin}`);
        window.location.href = `/session/${pin}/play/`;
    }

    /**
     * Обработать удаление сессии — перенаправить на главную.
     * @param {string} pin — PIN-код удалённой сессии
     */
    onSessionDeleted(pin) {
        console.log(`[WS] Сессия удалена: pin=${pin}`);
        window.location.href = "/?kicked=1";
    }

    /**
     * Попробовать переподключиться с exponential backoff.
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log("[WS] Превышено максимальное число попыток переподключения");
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            30000
        );
        console.log(`[WS] Переподключение через ${delay}мс (попытка ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    /**
     * Закрыть WebSocket-соединение вручную.
     */
    close() {
        if (this.ws) {
            this.ws.close(1000);
        }
    }
}


/**
 * Класс WebSocket-клиента для игровой сессии.
 *
 * Обрабатывает события:
 * - question_advanced — учитель переключил вопрос
 * - game_finished — игра завершена
 * - player_answered — игрок ответил (для хоста)
 */
class GameWebSocket {
    /**
     * Создать WebSocket-соединение для игровой сессии.
     * @param {string} pin — PIN-код игровой сессии
     * @param {number} currentQuestion — номер текущего вопроса (для сравнения)
     */
    constructor(pin, currentQuestion) {
        this.pin = pin;
        this.currentQuestion = currentQuestion;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.connect();
    }

    /**
     * Установить WebSocket-соединение с сервером.
     */
    connect() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/game/${this.pin}/`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log(`[WS] Game WebSocket подключен: pin=${this.pin}`);
            this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error("[WS] Ошибка парсинга JSON:", e);
            }
        };

        this.ws.onclose = (event) => {
            console.log(`[WS] Game WebSocket отключен: code=${event.code}`);
            if (event.code !== 1000) {
                this.attemptReconnect();
            }
        };

        this.ws.onerror = (error) => {
            console.error("[WS] Game WebSocket ошибка:", error);
        };
    }

    /**
     * Обработать входящее сообщение от сервера.
     * @param {Object} data — распарсенный JSON-объект сообщения
     */
    handleMessage(data) {
        switch (data.type) {
            case "question_advanced":
                this.onQuestionAdvanced(data.current_question, data.status);
                break;
            case "game_finished":
                this.onGameFinished(data.pin);
                break;
            case "game_state_update":
                this.onGameStateUpdate(data);
                break;
            case "player_answered":
                this.onPlayerAnswered(data.player_name, data.is_correct);
                break;
            default:
                console.log("[WS] Неизвестный тип сообщения:", data.type);
        }
    }

    /**
     * Обработать смену вопроса — перезагрузить страницу.
     * @param {number} newQuestion — номер нового вопроса
     * @param {string} status — статус сессии (in_progress, finished)
     */
    onQuestionAdvanced(newQuestion, status) {
        console.log(`[WS] Вопрос переключён: ${newQuestion}, статус: ${status}`);
        if (newQuestion !== this.currentQuestion || status === "finished") {
            window.location.reload();
        }
    }

    /**
     * Обработать завершение игры — перезагрузить страницу для результатов.
     * @param {string} pin — PIN-код завершённой сессии
     */
    onGameFinished(pin) {
        console.log(`[WS] Игра завершена: pin=${pin}`);
        window.location.reload();
    }

    /**
     * Обработать обновление состояния игры (для хоста).
     * @param {Object} data — полное состояние игры
     */
    onGameStateUpdate(data) {
        // Обновляем прогресс
        const progressEl = document.getElementById('gs-answered');
        if (progressEl) {
            progressEl.textContent = data.answered_count;
        }

        const totalEl = document.getElementById('gs-total-participants');
        if (totalEl) {
            totalEl.textContent = data.total_participants;
        }

        // Обновляем текущий вопрос
        const currentQEl = document.getElementById('gs-current-question');
        if (currentQEl) {
            currentQEl.textContent = data.current_question;
        }

        // Обновляем список игроков
        this.updatePlayersList(data.players);

        // Обновляем историю вопросов
        this.updateQuestionHistory(data.question_history);

        // Показываем/скрываем кнопку "Следующий вопрос"
        this.updateAdvanceButton(data.ready_for_next_question);

        console.log("[WS] Обновление состояния игры:", data);
    }

    /**
     * Обновить список игроков.
     * @param {Array} players — массив объектов {username, score, has_answered}
     */
    updatePlayersList(players) {
        const container = document.getElementById('gs-players');
        if (!container || !players) return;

        container.innerHTML = players.map(player => `
            <div class="player-row ${player.has_answered ? 'answered' : ''}">
                <span class="player-name">${escapeHtml(player.username)}</span>
                <span class="player-score">${player.score}</span>
            </div>
        `).join('');
    }

    /**
     * Обновить историю вопросов.
     * @param {Array} history — массив объектов с результатами вопросов
     */
    updateQuestionHistory(history) {
        const container = document.getElementById('gs-question-history');
        if (!container || !history) return;

        container.innerHTML = history.map(q => `
            <div class="question-result">
                <div class="question-text">Вопрос ${q.question_number}: ${escapeHtml(q.question_text)}</div>
                <div class="answers-summary">
                    Ответили: ${q.answered_count} / ${q.total_participants}
                </div>
            </div>
        `).join('');
    }

    /**
     * Обновить видимость кнопки "Следующий вопрос".
     * @param {boolean} ready — готовы ли к следующему вопросу
     */
    updateAdvanceButton(ready) {
        const promptEl = document.getElementById('gs-next-question-prompt');
        if (!promptEl) return;

        if (ready) {
            promptEl.style.display = 'block';
        } else {
            promptEl.style.display = 'none';
        }
    }

    /**
     * Обработать ответ игрока (для хоста).
     * @param {string} playerName — имя игрока
     * @param {boolean} isCorrect — правильный ли ответ
     */
    onPlayerAnswered(playerName, isCorrect) {
        console.log(`[WS] Игрок ${playerName} ответил (верно: ${isCorrect})`);

        // Можно добавить визуальную индикацию (например, уведомление)
        // Пока что просто логируем
    }

    /**
     * Попробовать переподключиться с exponential backoff.
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log("[WS] Превышено максимальное число попыток переподключения");
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            30000
        );
        console.log(`[WS] Переподключение через ${delay}мс (попытка ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    /**
     * Закрыть WebSocket-соединение вручную.
     */
    close() {
        if (this.ws) {
            this.ws.close(1000);
        }
    }
}

window.LobbyWebSocket = LobbyWebSocket;
window.GameWebSocket = GameWebSocket;