"""Threaded WebSocket client used by the GTK player."""

import json
import threading
from typing import Callable, Optional

import websocket


class WatchPartyClient:
    def __init__(
        self,
        server_url: str,
        name: str,
        on_message: Callable[[dict], None],
        on_closed: Callable[[str], None],
    ):
        self.server_url = server_url.rstrip("/") + "/ws"
        self.name = name
        self.on_message = on_message
        self.on_closed = on_closed
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self._hello: Optional[dict] = None
        self._closed_by_user = False
        self._send_lock = threading.Lock()

    def connect(self, action: str, code: str = "") -> None:
        self._hello = {"action": action, "name": self.name, "code": code}
        self._closed_by_user = False
        self.ws = websocket.WebSocketApp(
            self.server_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self.thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.thread.start()

    def _on_open(self, ws) -> None:
        ws.send(json.dumps(self._hello))

    def _on_message(self, _ws, message: str) -> None:
        try:
            self.on_message(json.loads(message))
        except (json.JSONDecodeError, TypeError):
            pass

    def _on_error(self, _ws, error) -> None:
        if not self._closed_by_user:
            self.on_closed(str(error))

    def _on_close(self, _ws, _status, reason) -> None:
        if not self._closed_by_user:
            self.on_closed(reason or "Connection closed.")

    def send(self, payload: dict) -> bool:
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            return False
        try:
            with self._send_lock:
                self.ws.send(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._closed_by_user = True
        if self.ws:
            self.ws.close()
        self.ws = None
