"""전역 스레드 안전 로그 버퍼 — Streamlit 실시간 로그 표시용"""
from __future__ import annotations

import threading
from datetime import datetime


class StreamLog:
    def __init__(self) -> None:
        self._lines: list[str] = []
        self._lock  = threading.Lock()

    # ── 로그 레벨 ─────────────────────────────────────────────────────────────
    def info(self, msg: str)  -> None: self._append("INFO ", msg)
    def warn(self, msg: str)  -> None: self._append("WARN ", msg)
    def error(self, msg: str) -> None: self._append("ERROR", msg)
    def step(self, msg: str)  -> None: self._append("▶    ", msg)
    def ok(self, msg: str)    -> None: self._append("✓    ", msg)

    def _append(self, level: str, msg: str) -> None:
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {level}  {msg}"
        with self._lock:
            self._lines.append(line)
        try:
            print(line, flush=True)
        except (UnicodeEncodeError, ValueError, OSError):
            pass  # 인코딩 오류 또는 파일 핸들 닫힘 무시 (Streamlit은 메모리 버퍼 사용)

    # ── 읽기 ─────────────────────────────────────────────────────────────────
    def get_all(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def get_recent(self, n: int = 80) -> list[str]:
        with self._lock:
            return self._lines[-n:]

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()


# 전역 싱글톤
geo_log = StreamLog()
