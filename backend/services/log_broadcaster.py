"""Bridge geo_log singleton to WebSocket clients."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket


class LogBroadcaster:
    """Polls geo_log and pushes new lines to connected WebSocket clients."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._last_index: dict[str, int] = {}
        self._active: dict[str, bool] = {}

    def register(self, brief_id: str, ws: "WebSocket"):
        self._connections.setdefault(brief_id, []).append(ws)

    def unregister(self, brief_id: str, ws: "WebSocket"):
        conns = self._connections.get(brief_id, [])
        if ws in conns:
            conns.remove(ws)

    def start(self, brief_id: str):
        self._active[brief_id] = True
        self._last_index[brief_id] = 0

    def stop(self, brief_id: str):
        self._active[brief_id] = False

    async def broadcast_loop(self, brief_id: str):
        from geo_cli.utils.stream_log import geo_log

        while self._active.get(brief_id, False) or self._connections.get(brief_id):
            lines = geo_log.get_all()
            last = self._last_index.get(brief_id, 0)
            new_lines = lines[last:]
            if new_lines:
                for ws in list(self._connections.get(brief_id, [])):
                    try:
                        for line in new_lines:
                            await ws.send_json({"type": "log", "line": line})
                    except Exception:
                        self.unregister(brief_id, ws)
                self._last_index[brief_id] = len(lines)
            await asyncio.sleep(0.3)


# Global singleton
log_broadcaster = LogBroadcaster()
