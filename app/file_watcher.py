"""File watcher using watchdog for live reload."""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

# Debounce interval in seconds
DEBOUNCE_INTERVAL = 0.5


class _DebouncedHandler(FileSystemEventHandler):
    """Debounced file system event handler to avoid rapid-fire updates."""

    def __init__(self, callback: Callable[[str], None], ignore_patterns: set[str]):
        super().__init__()
        self._callback = callback
        self._ignore_patterns = ignore_patterns
        self._last_event_time: float = 0.0
        self._timer: Optional[threading.Timer] = None
        self._last_path: Optional[str] = None
        self._lock = threading.Lock()

    def _should_ignore(self, path: str) -> bool:
        parts = Path(path).parts
        for part in parts:
            if part in self._ignore_patterns:
                return True
            for pat in self._ignore_patterns:
                if pat.startswith("*.") and part.endswith(pat[1:]):
                    return True
        return False

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return

        with self._lock:
            self._last_path = event.src_path
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_INTERVAL, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            path = self._last_path
        if path:
            self._callback(path)


class FileWatcher:
    """Watches a directory for file changes and triggers callbacks."""

    def __init__(self):
        self._observer: Optional[Observer] = None
        self._watch_path: Optional[str] = None
        self._on_change_callbacks: list[Callable[[str], None]] = []

    def add_callback(self, callback: Callable[[str], None]) -> None:
        self._on_change_callbacks.append(callback)

    def start(self, path: str) -> None:
        self.stop()
        if not path or not Path(path).is_dir():
            return

        self._watch_path = path

        ignore = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            "*.pyc", "*.pyo", ".DS_Store",
        }

        handler = _DebouncedHandler(
            callback=self._on_file_changed,
            ignore_patterns=ignore,
        )

        self._observer = Observer()
        self._observer.schedule(handler, path, recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            try:
                self._observer.join(timeout=2)
            except RuntimeError:
                pass
            self._observer = None

    def _on_file_changed(self, path: str) -> None:
        for cb in self._on_change_callbacks:
            try:
                cb(path)
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
