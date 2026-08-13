from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from daedalus.app import DaedalusApp, SessionState
from daedalus.sessions import SessionStore
from daedalus.ollama import OllamaModel


def test_app_resume_command(tmp_path, monkeypatch):
    ws_path = tmp_path.resolve()
    monkeypatch.setenv("DAEDALUS_HOME", str(ws_path / ".daedalus"))
    store = SessionStore(ws_path / ".daedalus" / "sessions")
    
    sess1 = store.create(str(ws_path), "gemma3:4b", title="First Session")
    sess1.append("user", "What is Python?")
    sess1.append("assistant", "Python is a programming language.")
    store.save(sess1)

    app = DaedalusApp(workspace_root=ws_path)
    app.models = [OllamaModel(name="gemma3:4b")]
    current_sess = store.create(str(ws_path), "gemma3:4b")
    app.state = SessionState(current=current_sess, workspace=app.workspace, model="gemma3:4b")

    # sess1 is index 2 because current_sess was created most recently
    handled = app._handle_command("/resume 2")
    assert handled is True
    assert app.state.current.id == sess1.id
    assert len(app.state.current.messages) == 2
    assert app.state.current.messages[0].content == "What is Python?"


def test_app_resume_token_on_startup(tmp_path, monkeypatch):
    ws_path = tmp_path.resolve()
    monkeypatch.setenv("DAEDALUS_HOME", str(ws_path / ".daedalus"))
    store = SessionStore(ws_path / ".daedalus" / "sessions")
    
    sess = store.create(str(ws_path), "gemma3:4b", title="Previous Convo")
    sess.append("user", "Hello world")
    sess.append("assistant", "Hello! How can I help?")
    store.save(sess)

    app = DaedalusApp(workspace_root=ws_path, resume_token="latest")
    app.ollama.list_models = MagicMock(return_value=[OllamaModel(name="gemma3:4b")])
    app.prompt.prompt = MagicMock(side_effect=KeyboardInterrupt)

    try:
        app.run()
    except KeyboardInterrupt:
        pass

    assert app.state is not None
    assert app.state.current.id == sess.id
    assert len(app.state.current.messages) == 2
    assert app.state.current.messages[0].content == "Hello world"
