"""Development server with auto-rebuild for aiseed-web sites.

Runs build.py against --site, watches the site's content/ data/ images/
plus the builder's own templates/ assets/. Serves <site>/build/.
"""

from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

BUILDER_ROOT = Path(__file__).resolve().parent.parent
DEBOUNCE_SEC = 0.4


def resolve_site(cli_value: str | None) -> Path:
    candidate = cli_value or os.environ.get("AISEED_WEB_SITE") or os.getcwd()
    site = Path(candidate).resolve()
    if not (site / "content").exists() and not (site / "data").exists():
        raise SystemExit(
            f"[serve] {site} does not look like an aiseed-web site. "
            "Pass --site <path> or set AISEED_WEB_SITE."
        )
    return site


class RebuildHandler(FileSystemEventHandler):
    def __init__(self, site: Path) -> None:
        self._site = site
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._stopped = False

    def on_any_event(self, event) -> None:
        if event.is_directory:
            return
        with self._lock:
            if self._stopped:
                return
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SEC, self._run_build)
            self._timer.daemon = True
            self._timer.start()

    def _run_build(self) -> None:
        print("[serve] change detected — rebuilding…", flush=True)
        result = subprocess.run(
            [sys.executable, str(BUILDER_ROOT / "tools" / "build.py"), "--site", str(self._site)],
        )
        if result.returncode != 0:
            print("[serve] build failed", flush=True)

    def cancel(self) -> None:
        with self._lock:
            self._stopped = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


def initial_build(site: Path) -> None:
    print("[serve] initial build…", flush=True)
    subprocess.run(
        [sys.executable, str(BUILDER_ROOT / "tools" / "build.py"), "--site", str(site)],
        check=True,
    )


def start_watcher(site: Path) -> tuple[Observer, RebuildHandler]:
    handler = RebuildHandler(site)
    observer = Observer()
    watch_dirs = [
        site / "content",
        site / "data",
        site / "images",
        BUILDER_ROOT / "templates",
        BUILDER_ROOT / "assets",
    ]
    for target in watch_dirs:
        if target.exists():
            observer.schedule(handler, str(target), recursive=True)
    observer.daemon = True
    observer.start()
    return observer, handler


def serve(build_dir: Path, port: int) -> None:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(build_dir), **kw)

        def log_message(self, format: str, *args) -> None:
            print(f"[http] {self.address_string()} — {format % args}", flush=True)

    with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
        print(f"[serve] http://localhost:{port} (Ctrl+C to stop)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[serve] shutting down", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Path to the site data directory.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-initial-build", action="store_true")
    args = parser.parse_args()

    site = resolve_site(args.site)
    if not args.no_initial_build:
        initial_build(site)

    observer, handler = start_watcher(site)
    try:
        serve(site / "build", args.port)
    finally:
        handler.cancel()
        observer.stop()
        observer.join(timeout=2)


if __name__ == "__main__":
    main()
