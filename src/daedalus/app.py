from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from .config import Config
from .messages import ChatMessage
from .ollama import OllamaClient, OllamaError, OllamaModel
from .rendering import (
    render_files_list,
    render_header,
    render_help_panel,
    render_models_table,
    render_sessions_table,
    render_themes_table,
    THEMES,
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
    def __init__(self, workspace_root: Path | None = None, resume_token: str | None = None) -> None:
        self.console = Console()
        self.config = Config.load()
        self.workspace = Workspace(workspace_root or self._default_workspace_root(), max_file_bytes=self.config.max_file_bytes)
        self.session_store = SessionStore()
        self.ollama = OllamaClient(self.config.host)
        self.prompt = PromptSession(history=InMemoryHistory(), completer=self._build_completer(), complete_while_typing=True)
        self.models: list[OllamaModel] = []
        self.state: SessionState | None = None
        self.resume_token = resume_token

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
                "/tree": None,
                "/sessions": {"": None},
                "/manage": None,
                "/new": None,
                "/clear": None,
                "/redraw": None,
                "/title": {"": None},
                "/model": None,
                "/theme": None,
                "/exit": None,
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
        session: SessionRecord | None = None

        if self.resume_token:
            all_sessions, _ = self.session_store.list_recent(self.config.recent_session_limit)
            workspace_sessions = [s for s in all_sessions if s.workspace_root == str(self.workspace.root)]

            if self.resume_token in ("latest", "last", "true", "1") and workspace_sessions:
                session = workspace_sessions[0]
            elif self.resume_token.isdigit():
                idx = int(self.resume_token) - 1
                if 0 <= idx < len(workspace_sessions):
                    session = workspace_sessions[idx]
            else:
                for s in all_sessions:
                    if s.id == self.resume_token or s.id.startswith(self.resume_token):
                        session = s
                        break
                if session is None:
                    try:
                        session = self.session_store.load(self.resume_token)
                    except (FileNotFoundError, ValueError):
                        session = None

        if session is None:
            session = self.session_store.create(str(self.workspace.root), model)
        else:
            if session.model and any(m.name == session.model for m in self.models):
                model = session.model

        self.state = SessionState(current=session, workspace=self.workspace, model=model)

        self._print_banner()
        if session.messages:
            self._print_session_history(session)
            for msg in session.messages:
                if msg.role == "user":
                    self.prompt.history.append_string(msg.content)
        try:
            with patch_stdout(raw=True):
                while True:
                    try:
                        user_text = self.prompt.prompt("> ")
                    except (EOFError, KeyboardInterrupt):
                        self.console.print()
                        break

                    text = user_text.strip()
                    if not text:
                        continue

                    if self._handle_command(text):
                        continue

                    self._chat(text)
        finally:
            if self.state and self.state.model:
                self.console.print(Text("Unloading model to free memory...", style="dim"))
                self.ollama.unload(self.state.model)

    def _select_initial_model(self) -> str:
        configured = self.config.model
        if configured and any(model.name == configured for model in self.models):
            return configured
        return self.models[0].name

    def _print_banner(self) -> None:
        assert self.state is not None
        file_count = len(self.workspace.list_files(max_items=10000))
        self.console.print(render_header(self.workspace.root, self.state.model, self.state.current, file_count, self.config.theme))
        self.console.print(Text("\n  Welcome to Daedalus. Type /help for commands.", style="bold white"))


    def _print_assistant_message(self, assistant_text: str) -> None:
        self.console.print(Text("Daedalus", style="bold cyan"))
        self.console.print(Text(assistant_text, style="white"))

    def _print_command_output(self, output: object) -> None:
        self.console.print(output)

    def _print_session_history(self, session: SessionRecord) -> None:
        if not session.messages:
            return
        self.console.print(Text("─── Previous conversation ───", style="dim"))
        for msg in session.messages:
            if msg.role == "user":
                self.console.print(Text(f"> {msg.content}", style="bold yellow"))
            elif msg.role == "assistant":
                self.console.print(Text("Daedalus", style="bold cyan"))
                self.console.print(Markdown(msg.content))
        self.console.print(Text("─── End of history ───", style="dim"))
        self.console.print()

    def _chat(self, user_text: str) -> None:
        assert self.state is not None
        self.state.current.append("user", user_text)
        if self.state.current.title == "Untitled session":
            self.state.current.title = summarize_title(user_text)

        context_messages = self._build_messages(user_text)
        partial = ""

        self.console.print(Text("Daedalus", style="bold cyan"))
        try:
            for chunk in self.ollama.stream_chat(self.state.model, context_messages):
                partial += chunk
                self.console.print(Text(chunk, style="white"), end="")
        except KeyboardInterrupt:
            self.console.print(Text(" [Interrupted]", style="dim"), end="")
        except OllamaError as exc:
            error_text = f"Error: {exc}"
            self.console.print(Text(error_text, style="red"))
            self.state.current.append("assistant", error_text)
            self.session_store.save(self.state.current)
            return

        self.console.print()

        assistant_text = partial.strip() or ""
        self.state.current.append("assistant", assistant_text)
        self.session_store.save(self.state.current)

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
            self._print_command_output(render_help_panel())
            return True

        if text == "/pwd":
            self._print_command_output(f"Workspace: {self.workspace.root}")
            return True

        if text.startswith("/files") or text.startswith("/fiels"):
            parts = text.split(maxsplit=1)
            target = self.workspace.root
            if len(parts) > 1:
                resolved = self.workspace.resolve_directory(parts[1].strip())
                if resolved is None:
                    self._print_command_output(Text("Directory not found in this workspace.", style="red"))
                    return True
                target = resolved
            self._print_command_output(render_files_list(self.workspace.list_files(path=target)))
            return True

        if text.startswith("/tree"):
            parts = text.split(maxsplit=1)
            target = self.workspace.root
            if len(parts) > 1:
                resolved = self.workspace.resolve_directory(parts[1].strip())
                if resolved is None:
                    self._print_command_output(Text("Directory not found in this workspace.", style="red"))
                    return True
                target = resolved
            self._print_command_output(Text(self.workspace.tree(path=target), style="cyan"))
            return True

        if text.startswith("/sessions") or text.startswith("/session") or text.startswith("/resume"):
            parts = text.split(maxsplit=1)
            token = parts[1].strip() if len(parts) > 1 else ""
            if token:
                self._resume_session(token)
            else:
                self._browse_sessions()
            return True

        if text.startswith("/manage"):
            self._manage_sessions()
            return True

        if text == "/clear":
            self.state.current.messages.clear()
            self.session_store.save(self.state.current)
            self.console.clear()
            self._print_banner()
            self._print_command_output(Text("Conversation cleared.", style="green"))
            return True

        if text == "/title":
            self._print_command_output(self.state.current.title)
            return True

        if text.startswith("/title "):
            parts = text.split(maxsplit=1)
            self.state.current.title = parts[1].strip()
            self.session_store.save(self.state.current)
            self._print_command_output(f"Title set to: {self.state.current.title}")
            return True

        if text == "/new":
            self.state.current = self.session_store.create(str(self.workspace.root), self.state.model)
            self._print_command_output("Started a new session.")
            return True

        if text == "/redraw":
            self._print_banner()
            return True

        if text == "/model":
            self._select_model_interactively()
            return True

        if text == "/theme":
            self._select_theme_interactively()
            return True

        if text.startswith("/"):
            self._print_command_output(Text("Unknown command.", style="yellow"))
            return True

        return False

    def _resume_session(self, token: str, sessions: list[SessionRecord] | None = None) -> None:
        assert self.state is not None
        if sessions is None:
            all_sessions, _ = self.session_store.list_recent(self.config.recent_session_limit)
            sessions = [s for s in all_sessions if s.workspace_root == str(self.workspace.root)]
        session: SessionRecord | None = None
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(sessions):
                session = sessions[index]
        else:
            for s in sessions:
                if s.id == token or s.id.startswith(token):
                    session = s
                    break
            if session is None:
                try:
                    session = self.session_store.load(token)
                except (FileNotFoundError, ValueError):
                    session = None

        if session is None:
            self._print_command_output(Text(f"Session '{token}' not found.", style="red"))
            return

        if session.workspace_root != str(self.workspace.root):
            self.console.print(Text(f"  ⚠ This session is from a different workspace: {session.workspace_root}", style="bold yellow"))

        self.state.current = session
        if session.model and any(model.name == session.model for model in self.models):
            self.state.model = session.model

        for msg in session.messages:
            if msg.role == "user":
                self.prompt.history.append_string(msg.content)

        self._print_command_output(Text(f"Resumed: {session.title} ({len(session.messages)} messages)", style="green"))
        self._print_banner()
        self._print_session_history(session)

    def _browse_sessions(self) -> None:
        assert self.state is not None
        status_message: str | None = None
        status_style: str = "green"
        while True:
            all_sessions, _ = self.session_store.list_recent(self.config.recent_session_limit)
            sessions = [s for s in all_sessions if s.workspace_root == str(self.workspace.root)]
            self.console.clear()
            self._print_banner()

            if status_message:
                self.console.print(Text(f"  {status_message}", style=status_style))
                status_message = None

            if not sessions:
                self.console.print("[yellow]No sessions for this workspace.[/yellow]")
                return

            self.console.print(render_sessions_table(sessions))
            self.console.print(Text("  Enter a number to resume, 'd <number>' to delete, 'n' for new session, or Enter to cancel.", style="dim"))
            choice = self.prompt.prompt("Session> ").strip()
            if not choice:
                self.console.clear()
                self._print_banner()
                return
            if choice.startswith("/"):
                self.console.clear()
                self._print_banner()
                self._handle_command(choice)
                return
            if choice.lower() == "n":
                self.state.current = self.session_store.create(str(self.workspace.root), self.state.model)
                self.console.clear()
                self._print_banner()
                self._print_command_output(Text("Started a new session.", style="green"))
                return

            if choice.lower().startswith("d "):
                parts = choice.split(maxsplit=1)
                if len(parts) > 1:
                    target = parts[1].strip()
                    status_message, status_style = self._delete_session(target, sessions)
                    continue

            self._resume_session(choice, sessions)
            return

    def _manage_sessions(self) -> None:
        assert self.state is not None
        status_message: str | None = None
        status_style: str = "green"
        while True:
            sessions, total = self.session_store.list_recent(self.config.recent_session_limit)
            self.console.clear()
            self._print_banner()

            if status_message:
                self.console.print(Text(f"  {status_message}", style=status_style))
                status_message = None

            if not sessions:
                self.console.print("[yellow]No saved sessions yet.[/yellow]")
                return

            visible = len(sessions)
            hidden = total - visible
            self.console.print(Text(f"  Showing {visible} of {total} sessions", style="dim"))
            if hidden > 0:
                self.console.print(Text(f"  ⚠ {hidden} older sessions are hidden. Delete unused sessions to see them.", style="bold red"))

            self.console.print(render_sessions_table(sessions))
            self.console.print(Text("  Enter 'd <number>' to delete a session, or Enter to go back.", style="dim"))
            choice = self.prompt.prompt("Manage> ").strip()
            if not choice:
                self.console.clear()
                self._print_banner()
                return
            if choice.startswith("/"):
                self.console.clear()
                self._print_banner()
                self._handle_command(choice)
                return

            if choice.lower().startswith("d "):
                parts = choice.split(maxsplit=1)
                if len(parts) > 1:
                    target = parts[1].strip()
                    status_message, status_style = self._delete_session(target, sessions)
                    continue

            self.console.print(Text("  Use 'd <number>' to delete or press Enter to go back.", style="yellow"))

    def _delete_session(self, token: str, sessions: list[SessionRecord]) -> tuple[str, str]:
        assert self.state is not None
        session_to_delete: SessionRecord | None = None
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(sessions):
                session_to_delete = sessions[index]
        else:
            try:
                session_to_delete = self.session_store.load(token)
            except FileNotFoundError:
                session_to_delete = None

        if session_to_delete is None:
            return "Session not found.", "red"

        if session_to_delete.id == self.state.current.id:
            return "Cannot delete the active session. Start a new session or switch first.", "red"

        try:
            self.session_store.delete(session_to_delete.id)
            return f"Deleted session: {session_to_delete.title}", "green"
        except OSError as exc:
            return f"Failed to delete session: {exc}", "red"

    def _select_model_interactively(self) -> None:
        assert self.state is not None
        self.console.print(render_models_table(self.models, self.state.model))
        choice = self.prompt.prompt("Select model number or name (Enter to cancel): ").strip()
        if not choice:
            return
        if choice.startswith("/"):
            self._handle_command(choice)
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
            self._print_command_output(Text("Invalid model selection.", style="red"))
            return

        self.state.model = selected
        self.state.current.model = selected
        self.session_store.save(self.state.current)
        self.config.model = selected
        self.config.save()
        self._print_command_output(Text(f"Model set to {selected}", style="green"))

    def _select_theme_interactively(self) -> None:
        assert self.state is not None
        self.console.print(render_themes_table(THEMES, self.config.theme))
        choice = self.prompt.prompt("Select theme number or name (Enter to cancel): ").strip()
        if not choice:
            return

        selected = None
        theme_keys = list(THEMES.keys())
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(theme_keys):
                selected = theme_keys[index]
        else:
            choice_lower = choice.lower()
            for key, theme in THEMES.items():
                if key == choice_lower or theme.name.lower() == choice_lower:
                    selected = key
                    break

        if selected is None:
            self._print_command_output(Text("Invalid theme selection.", style="red"))
            return

        self.config.theme = selected
        self.config.save()
        self._print_command_output(Text(f"Theme set to {THEMES[selected].name}", style="green"))
        self._print_banner()

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Daedalus AI CLI")
    parser.add_argument("-r", "--resume", nargs="?", const="latest", help="Resume recent session (or specify session number/ID)")
    parser.add_argument("-s", "--session", help="Resume specified session ID or number")
    args = parser.parse_args()

    resume_token = args.session or args.resume
    app = DaedalusApp(resume_token=resume_token)
    app.run()

