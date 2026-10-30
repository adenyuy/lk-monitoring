"""Siaran peristiwa ke UI (Server-Sent Events).

Thread mana pun bisa `publish(...)`; endpoint /api/events membaca peristiwa baru
berdasarkan id terakhir yang sudah dikirim ke browser.
"""

import threading
import time
from collections import deque
from typing import Any

_lock = threading.Lock()
_buf: deque[dict[str, Any]] = deque(maxlen=500)
_next_id = 1


def publish(type_: str, **data: Any) -> None:
    global _next_id
    with _lock:
        _buf.append({"id": _next_id, "type": type_, "time": time.time(), "data": data})
        _next_id += 1


def since(last_id: int) -> list[dict[str, Any]]:
    with _lock:
        return [e for e in _buf if e["id"] > last_id]


def last_id() -> int:
    with _lock:
        return _next_id - 1
