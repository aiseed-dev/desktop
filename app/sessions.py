"""Session management for Claude Code conversations."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

SESSIONS_FILE = Path.home() / ".flet-claude" / "sessions.json"


@dataclass
class Session:
    session_id: str
    name: str
    project_dir: str
    created_at: str = ""
    last_message: str = ""
    total_cost: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class SessionManager:
    def __init__(self):
        self.sessions: list[Session] = []
        self._load()

    def _load(self) -> None:
        if SESSIONS_FILE.exists():
            try:
                data = json.loads(SESSIONS_FILE.read_text())
                self.sessions = [Session(**s) for s in data]
            except (json.JSONDecodeError, TypeError):
                self.sessions = []

    def _save(self) -> None:
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSIONS_FILE.write_text(
            json.dumps([asdict(s) for s in self.sessions], indent=2, ensure_ascii=False)
        )

    def add(self, session: Session) -> None:
        self.sessions.insert(0, session)
        self._save()

    def update(self, session_id: str, last_message: str = "", cost: Optional[float] = None) -> None:
        for s in self.sessions:
            if s.session_id == session_id:
                if last_message:
                    s.last_message = last_message
                if cost is not None:
                    s.total_cost += cost
                break
        self._save()

    def get(self, session_id: str) -> Optional[Session]:
        for s in self.sessions:
            if s.session_id == session_id:
                return s
        return None

    def list_all(self) -> list[Session]:
        return list(self.sessions)

    def delete(self, session_id: str) -> None:
        self.sessions = [s for s in self.sessions if s.session_id != session_id]
        self._save()
