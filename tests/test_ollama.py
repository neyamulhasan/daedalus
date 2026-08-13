from __future__ import annotations

import httpx

from daedalus.messages import ChatMessage
from daedalus.ollama import OllamaClient


def test_list_models(monkeypatch):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"models": [{"name": "gemma3:4b", "size": 123, "modified_at": "now"}]})
        if request.url.path == "/api/tags"
        else httpx.Response(404)
    )

    def fake_get(url, timeout):
        return httpx.Client(transport=transport).get(url, timeout=timeout)

    monkeypatch.setattr("daedalus.ollama.httpx.get", fake_get)

    client = OllamaClient("http://localhost:11434")
    models = client.list_models()

    assert models[0].name == "gemma3:4b"


def test_stream_chat(monkeypatch):
    class FakeStreamResponse:
        def __init__(self) -> None:
            self.status_code = 200

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            yield '{"message":{"content":"hello"},"done":false}'
            yield '{"message":{"content":" world"},"done":true}'

    class FakeContextManager:
        def __enter__(self):
            return FakeStreamResponse()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("daedalus.ollama.httpx.stream", lambda *args, **kwargs: FakeContextManager())

    client = OllamaClient("http://localhost:11434")
    chunks = list(client.stream_chat("gemma3:4b", [ChatMessage(role="user", content="hello")]))

    assert chunks == ["hello", " world"]
