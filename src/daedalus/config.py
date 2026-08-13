from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any
import tomllib


def daedalus_home() -> Path:
    override = os.environ.get("DAEDALUS_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".daedalus"


def config_path() -> Path:
    return daedalus_home() / "config.toml"


def sessions_dir() -> Path:
    return daedalus_home() / "sessions"


@dataclass(slots=True)
class Config:
    host: str = "http://127.0.0.1:11434"
    model: str | None = None
    max_history_messages: int = 24
    max_file_bytes: int = 200_000
    recent_session_limit: int = 20

    @classmethod
    def default(cls) -> "Config":
        return cls()

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if not path.exists():
            return cls.default()

        data = tomllib.loads(path.read_text(encoding="utf-8"))
        model = str(data.get("model", "")).strip() or None
        return cls(
            host=str(data.get("host", cls().host)),
            model=model,
            max_history_messages=int(data.get("max_history_messages", cls().max_history_messages)),
            max_file_bytes=int(data.get("max_file_bytes", cls().max_file_bytes)),
            recent_session_limit=int(data.get("recent_session_limit", cls().recent_session_limit)),
        )

    def save(self) -> None:
        home = daedalus_home()
        home.mkdir(parents=True, exist_ok=True)
        sessions_dir().mkdir(parents=True, exist_ok=True)
        config_path().write_text(self.to_toml(), encoding="utf-8")

    def to_toml(self) -> str:
        lines = [f'host = "{self.host}"']
        lines.append(f'model = "{self.model or ""}"')
        lines.append(f"max_history_messages = {self.max_history_messages}")
        lines.append(f"max_file_bytes = {self.max_file_bytes}")
        lines.append(f"recent_session_limit = {self.recent_session_limit}")
        return "\n".join(lines) + "\n"

