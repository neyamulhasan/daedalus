from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str

