from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

import httpx

from .messages import ChatMessage


@dataclass(slots=True)
class OllamaModel:
    name: str
    size: int | None = None
    modified_at: str | None = None


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def list_models(self) -> list[OllamaModel]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Unable to reach Ollama at {self.base_url}: {exc}") from exc

        payload = response.json()
        models = payload.get("models", [])
        return [
            OllamaModel(
                name=str(model.get("name", "")),
                size=int(model.get("size")) if model.get("size") is not None else None,
                modified_at=model.get("modified_at"),
            )
            for model in models
            if isinstance(model, dict) and model.get("name")
        ]

    def stream_chat(self, model: str, messages: list[ChatMessage]) -> Iterable[str]:
        payload = {
            "model": model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "stream": True,
        }

        try:
            with httpx.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=None) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    content = message.get("content")
                    if content:
                        yield str(content)
                    if data.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama chat request failed: {exc}") from exc

    def unload(self, model: str) -> bool:
        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0},
                timeout=10.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
