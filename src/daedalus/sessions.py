from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .config import sessions_dir
from .messages import ChatMessage


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def relative_time_label(iso_timestamp: str) -> str:
    try:
        moment = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return iso_timestamp

    delta = datetime.now(tz=timezone.utc) - moment
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s ago"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def summarize_title(text: str, limit: int = 40) -> str:
    title = " ".join(text.strip().split())
    if not title:
        return "Untitled session"
    return title[:limit].rstrip()


@dataclass(slots=True)
class SessionRecord:
    id: str
    title: str
    workspace_root: str
    model: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage] = field(default_factory=list)

    @classmethod
    def create(cls, workspace_root: str, model: str, title: str = "Untitled session") -> "SessionRecord":
        timestamp = utc_now_iso()
        return cls(
            id=str(uuid4()),
            title=title,
            workspace_root=workspace_root,
            model=model,
            created_at=timestamp,
            updated_at=timestamp,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SessionRecord":
        raw_messages = data.get("messages", [])
        messages: list[ChatMessage] = []
        for item in raw_messages:
            if isinstance(item, dict):
                messages.append(ChatMessage(role=str(item.get("role", "user")), content=str(item.get("content", ""))))

        return cls(
            id=str(data.get("id", str(uuid4()))),
            title=str(data.get("title", "Untitled session")),
            workspace_root=str(data.get("workspace_root", "")),
            model=str(data.get("model", "")),
            created_at=str(data.get("created_at", utc_now_iso())),
            updated_at=str(data.get("updated_at", utc_now_iso())),
            messages=messages,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "workspace_root": self.workspace_root,
            "model": self.model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [asdict(message) for message in self.messages],
        }

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def append(self, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))
        self.touch()


class SessionStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or sessions_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str) -> Path:
        clean_id = session_id.removesuffix(".json")
        return self.base_dir / f"{clean_id}.json"

    def create(self, workspace_root: str, model: str, title: str = "Untitled session") -> SessionRecord:
        session = SessionRecord.create(workspace_root=workspace_root, model=model, title=title)
        self.save(session)
        return session

    def save(self, session: SessionRecord) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path_for(session.id).write_text(json.dumps(session.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def load(self, session_id: str) -> SessionRecord:
        clean_id = session_id.removesuffix(".json")
        path = self.path_for(clean_id)
        if not path.exists():
            raise FileNotFoundError(f"Session file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid session data")
        return SessionRecord.from_dict(data)

    def list_recent(self, limit: int = 100) -> tuple[list[SessionRecord], int]:
        sessions: list[SessionRecord] = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    sessions.append(SessionRecord.from_dict(data))
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue

        sessions.sort(key=lambda session: session.updated_at, reverse=True)
        total = len(sessions)
        return sessions[:limit], total

    def delete(self, session_id: str) -> None:
        path = self.path_for(session_id)
        if path.exists():
            path.unlink()

