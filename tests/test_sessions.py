from __future__ import annotations

from daedalus.sessions import SessionStore, summarize_title


def test_session_round_trip(tmp_path):
    store = SessionStore(tmp_path)
    session = store.create("/workspace", "gemma3:4b")
    session.append("user", "hello")
    session.append("assistant", "hi")
    store.save(session)

    loaded = store.load(session.id)

    assert loaded.id == session.id
    assert loaded.messages[0].content == "hello"
    assert loaded.messages[1].content == "hi"


def test_session_load_with_json_suffix(tmp_path):
    store = SessionStore(tmp_path)
    session = store.create("/workspace", "gemma3:4b")
    session.append("user", "hello suffix")
    store.save(session)

    loaded_with_suffix = store.load(f"{session.id}.json")
    assert loaded_with_suffix.id == session.id
    assert loaded_with_suffix.messages[0].content == "hello suffix"


def test_summarize_title():
    assert summarize_title("   explain example.cpp   ") == "explain example.cpp"

