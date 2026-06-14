/*
 * Клиент WebSocket для лобби и игровых сессий.
 *
 * Заменяет HTTP-polling: одно постоянное соединение, сервер сам
 * присылает обновления. При обрыве — авто-переподключение с
 * экспоненциальной задержкой и запросом свежего снимка (action: sync).
 */
(function (global) {
    "use strict";

    function escapeHtml(str) {
        return String(str == null ? "" : str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function LobbyWebSocket(pin, options) {
        options = options || {};
        this.pin = pin;
        // Путь можно задать явно (например '/ws/admin/'); по умолчанию —
        // эндпоинт лобби по PIN.
        this.path = options.path || ("/ws/lobby/" + pin + "/");
        this.ws = null;
        this.handlers = {};
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.manualClose = false;
        this.connect();
    }

    LobbyWebSocket.prototype.on = function (type, callback) {
        this.handlers[type] = callback;
        return this;
    };

    LobbyWebSocket.prototype.connect = function () {
        var protocol = global.location.protocol === "https:" ? "wss:" : "ws:";
        var url = protocol + "//" + global.location.host + this.path;
        var self = this;

        this.ws = new WebSocket(url);

        this.ws.onopen = function () {
            self.reconnectAttempts = 0;
        };

        this.ws.onmessage = function (event) {
            var data;
            try {
                data = JSON.parse(event.data);
            } catch (e) {
                return;
            }
            var handler = self.handlers[data.type];
            if (handler) {
                handler(data);
            }
        };

        this.ws.onclose = function () {
            if (!self.manualClose) {
                self.reconnect();
            }
        };

        this.ws.onerror = function () {
            // onclose сработает следом — переподключение там.
        };
    };

    LobbyWebSocket.prototype.reconnect = function () {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            return;
        }
        this.reconnectAttempts++;
        var delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 15000);
        var self = this;
        setTimeout(function () {
            self.connect();
        }, delay);
    };

    LobbyWebSocket.prototype.sync = function () {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: "sync" }));
        }
    };

    LobbyWebSocket.prototype.close = function () {
        this.manualClose = true;
        if (this.ws) {
            this.ws.close();
        }
    };

    global.LobbyWebSocket = LobbyWebSocket;
    global.wsEscapeHtml = escapeHtml;
})(window);
