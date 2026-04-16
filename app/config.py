"""Configuration management for Flet Claude Code GUI."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".flet-claude"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    project_dir: str = ""
    model: str = "sonnet"
    theme: str = "dark"
    build_command: str = ""
    deploy_command: str = ""
    image_dir: str = "images"
    image_max_width: int = 1200
    image_format: str = "webp"
    window_width: int = 1400
    window_height: int = 900

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls) -> "AppConfig":
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()
