from __future__ import annotations

import os

from dataclasses import dataclass
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.live import Live
from rich.console import RenderableType
from .config import Config
from .messages import ChatMessage
from .ollama import OllamaClient, OllamaError, OllamaModel
from .rendering import (
    render_conversation_box,
    render_files_list,
    render_footer,
    render_header,
    render_help_panel,
    render_models_table,
    render_sessions_table,
    render_transcript,
)
from .sessions import SessionRecord, SessionStore, summarize_title
from .workspace import Workspace, extract_file_references, looks_like_file_request, looks_like_project_question


SYSTEM_PROMPT = (
    "You are Daedalus, a fast local assistant for a developer's current project. "
    "Be concise, helpful, and use only the workspace context provided."
)


@dataclass(slots=True)
class SessionState:
    current: SessionRecord
    workspace: Workspace
    model: str


class DaedalusApp:
    def __init__(self, workspace_root: Path | None = None) -> None:
        self.console = Console()
        self.config = Config.load()
        self.workspace = Workspace(workspace_root or self._default_workspace_root(), max_file_bytes=self.config.max_file_bytes)
        self.session_store = SessionStore()
        self.ollama = OllamaClient(self.config.host)
        self.prompt = PromptSession(history=InMemoryHistory(), completer=self._build_completer(), complete_while_typing=True)
        self.models: list[OllamaModel] = []
        self.state: SessionState | None = None
        self.notice: RenderableType | None = None

    def _default_workspace_root(self) -> Path:
        candidate = os.environ.get("DAEDALUS_WORKSPACE") or os.environ.get("PWD")
        if candidate:
            path = Path(candidate).expanduser()
            if path.exists() and path.is_dir():
                return path.resolve()
        return Path.cwd().resolve()

    def _build_completer(self) -> NestedCompleter:
        return NestedCompleter.from_nested_dict(
            {
                "/help": None,
                "/pwd": None,
                "/files": None,
                "/fiels": None,
                "/tree": None,
                "/sessions": None,
                "/resume": {"": None},
                "/new": None,
                "/clear": None,
                "/title": {"": None},
                "/model": None,
                "/exit": None,
                "/quit": None,
            }
        )

    def run(self) -> None:
        try:
            self.models = self.ollama.list_models()
        except OllamaError as exc:
            self.console.print(f"[red]{exc}[/red]")
            raise SystemExit(1) from exc

        if not self.models:
            self.console.print("[red]No Ollama models are installed. Run `ollama pull <model>` first.[/red]")
            raise SystemExit(1)

        model = self._select_initial_model()
        session = self.session_store.create(str(self.workspace.root), model)
        self.state = SessionState(current=session, workspace=self.workspace, model=model)

        self._render()
        with patch_stdout(raw=True):
            while True:
                try:
                    user_text = self.prompt.prompt("❯ ")
                except (EOFError, KeyboardInterrupt):
                    self.console.print()
                    break

                text = user_text.strip()
                if not text:
                    continue

                if self._handle_command(text):
                    self._render()
                    continue

                self._chat(text)

    def _select_initial_model(self) -> str:
        configured = self.config.model
        if configured and any(model.name == configured for model in self.models):
            return configured
        return self.models[0].name

    def _render(self) -> None:
        assert self.state is not None
        self.console.clear()
        self.console.print(render_header(str(self.workspace.root), self.state.model, self.state.current))
        if self.notice is not None:
            self.console.print(self.notice)
        self.console.print(render_conversation_box(self.state.current.messages, max_messages=self._max_visible_messages()))
        self.console.print(render_footer(self.state.model, str(self.workspace.root), self.state.current))

    def _chat(self, user_text: str) -> None:
        assert self.state is not None
        self.notice = None
        self.state.current.append("user", user_text)
        if self.state.current.title == "Untitled session":
            self.state.current.title = summarize_title(user_text)

        context_messages = self._build_messages(user_text)
        partial = ""

        with Live(
            render_conversation_box(
                self.state.current.messages,
                partial_assistant=partial,
                max_messages=self._max_visible_messages(),
            ),
            console=self.console,
            refresh_per_second=20,
            transient=True,
        ) as live:
            try:
                for chunk in self.ollama.stream_chat(self.state.model, context_messages):
                    partial += chunk
                    live.update(
                        render_conversation_box(
                            self.state.current.messages,
                            partial_assistant=partial,
                            max_messages=self._max_visible_messages(),
                        )
                    )
            except OllamaError as exc:
                self.state.current.append("assistant", f"Error: {exc}")
                self.session_store.save(self.state.current)
                self._render()
                return

        assistant_text = partial.strip() or ""
        self.state.current.append("assistant", assistant_text)
        self.session_store.save(self.state.current)
        self._render()

    def _max_visible_messages(self) -> int:
        height = max(20, self.console.size.height)
        reserved = 12
        approx_lines_per_message = 5
        available = max(1, height - reserved)
        return max(2, available // approx_lines_per_message)

    def _build_messages(self, user_text: str) -> list[ChatMessage]:
        assert self.state is not None
        messages: list[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        context = self._build_file_context(user_text)
        if context:
            messages.append(ChatMessage(role="system", content=context))

        messages.extend(self.state.current.messages[-self.config.max_history_messages :])
        return messages

    def _build_file_context(self, user_text: str) -> str | None:
        references = extract_file_references(user_text)
        if not references and not looks_like_file_request(user_text):
            return None

        resolved_entries: list[str] = []
        for reference in references:
            path = self.workspace.resolve_reference(reference)
            if path is None:
                continue
            try:
                content = self.workspace.read_text_file(path)
            except (OSError, ValueError):
                continue
            resolved_entries.append(f"File: {self.workspace.relative_path(path)}\n{content}")

        if not resolved_entries and looks_like_project_question(user_text):
            files = self.workspace.list_files()
            if not files:
                return "Workspace files: none found."
            return "Workspace files:\n" + "\n".join(f"- {item}" for item in files)

        if not resolved_entries:
            return None

        return "Relevant workspace files:\n\n" + "\n\n".join(resolved_entries)

    def _handle_command(self, text: str) -> bool:
        assert self.state is not None
        if text in {"/quit", "/exit"}:
            raise SystemExit(0)

        if text == "/help":
            self.notice = render_help_panel()
            return True

        if text == "/pwd":
            self.notice = f"Workspace: {self.workspace.root}"
            return True

        if text.startswith("/files") or text.startswith("/fiels"):
            parts = text.split(maxsplit=1)
            target = self.workspace.root
            if len(parts) > 1:
                resolved = self.workspace.resolve_directory(parts[1].strip())
                if resolved is None:
                    self.notice = "[red]Directory not found in this workspace.[/red]"
                    return True
                target = resolved
            self.notice = render_files_list(self.workspace.list_files(path=target))
            return True

        if text.startswith("/tree"):
            parts = text.split(maxsplit=1)
            target = self.workspace.root
            if len(parts) > 1:
                resolved = self.workspace.resolve_directory(parts[1].strip())
                if resolved is None:
                    self.notice = "[red]Directory not found in this workspace.[/red]"
                    return True
                target = resolved
            self.notice = f"[cyan]{self.workspace.tree(path=target)}[/cyan]"
            return True

        if text == "/sessions":
            sessions = self.session_store.list_recent(self.config.recent_session_limit)
            self.notice = render_sessions_table(sessions)
            return True

        if text == "/clear":
            self.state.current.messages.clear()
            self.session_store.save(self.state.current)
            self.notice = "Conversation cleared."
            return True

        if text == "/title":
            self.notice = self.state.current.title
            return True

        if text.startswith("/title "):
            parts = text.split(maxsplit=1)
            self.state.current.title = parts[1].strip()
            self.session_store.save(self.state.current)
            self.notice = f"Title set to: {self.state.current.title}"
            return True

        if text == "/new":
            self.state.current = self.session_store.create(str(self.workspace.root), self.state.model)
            self.notice = "Started a new session."
            return True

        if text.startswith("/resume"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                self._resume_session_interactively()
            else:
                self._resume_session(parts[1].strip())
            return True

        if text == "/model":
            self._select_model_interactively()
            return True

        if text.startswith("/"):
            self.notice = "[yellow]Unknown command.[/yellow]"
            return True

        return False

    def _resume_session(self, token: str) -> None:
        assert self.state is not None
        sessions = self.session_store.list_recent(self.config.recent_session_limit)
        session: SessionRecord | None = None
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(sessions):
                session = sessions[index]
        else:
            try:
                session = self.session_store.load(token)
            except FileNotFoundError:
                session = None

        if session is None:
            self.notice = "[red]Session not found.[/red]"
            return

        self.state.current = session
        if session.model and any(model.name == session.model for model in self.models):
            self.state.model = session.model
        self.notice = f"[green]Resumed[/green] {session.title}"

    def _resume_session_interactively(self) -> None:
        assert self.state is not None
        sessions = self.session_store.list_recent(self.config.recent_session_limit)
        if not sessions:
            self.console.print("[yellow]No saved sessions yet.[/yellow]")
            return

        self.console.print(render_sessions_table(sessions))
        choice = self.prompt.prompt("Select session number or id (Enter to cancel): ").strip()
        if not choice:
            return
        self._resume_session(choice)

    def _select_model_interactively(self) -> None:
        assert self.state is not None
        self.console.print(render_models_table(self.models, self.state.model))
        choice = self.prompt.prompt("Select model number or name (Enter to cancel): ").strip()
        if not choice:
            return

        selected = None
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(self.models):
                selected = self.models[index].name
        else:
            for model in self.models:
                if model.name == choice:
                    selected = choice
                    break

        if selected is None:
            self.notice = "[red]Invalid model selection.[/red]"
            return

        self.state.model = selected
        self.state.current.model = selected
        self.session_store.save(self.state.current)
        self.config.model = selected
        self.config.save()
        self.notice = f"[green]Model set to[/green] {selected}"


def main() -> None:
    app = DaedalusApp()
    app.run()

