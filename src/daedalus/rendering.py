from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .messages import ChatMessage
from .ollama import OllamaModel
from .sessions import SessionRecord, relative_time_label


def render_header(workspace_root: str, model: str, session: SessionRecord | None = None) -> Panel:
    title = Text()
    title.append("DAEDALUS", style="bold white")
    title.append(f"    {model}", style="bold cyan")
    if session is not None:
        title.append(f"    {session.title}", style="dim")

    body = Text()
    body.append("Workspace: ", style="dim")
    body.append(workspace_root, style="green")
    return Panel(Group(title, body), box=box.ROUNDED, border_style="blue", padding=(0, 1))


def render_transcript(messages: list[ChatMessage], partial_assistant: str | None = None) -> RenderableType:
    blocks: list[RenderableType] = []
    for message in messages:
        if message.role == "user":
            blocks.append(_message_panel("You", message.content, "yellow", markdown=False))
        elif message.role == "assistant":
            blocks.append(_message_panel("Daedalus", message.content, "cyan", markdown=True))

    if partial_assistant is not None:
        blocks.append(_message_panel("Daedalus", partial_assistant, "cyan", markdown=False))

    if not blocks:
        return render_welcome_panel()
    return Group(*blocks)


def render_models_table(models: list[OllamaModel], current_model: str) -> Table:
    table = Table(title="Models", box=box.ROUNDED, show_lines=False)
    table.add_column("#", width=4, justify="right")
    table.add_column("Current", width=8)
    table.add_column("Model", style="cyan")
    table.add_column("Size", justify="right")

    for index, model in enumerate(models, start=1):
        marker = "●" if model.name == current_model else ""
        size_text = "-" if model.size is None else f"{model.size:,}"
        table.add_row(str(index), marker, model.name, size_text)
    return table


def render_sessions_table(sessions: list[SessionRecord]) -> Table:
    table = Table(title="Recent sessions", box=box.ROUNDED, show_lines=False)
    table.add_column("#", justify="right", width=4)
    table.add_column("Title", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Last Active", style="dim")

    for index, session in enumerate(sessions, start=1):
        table.add_row(str(index), session.title, session.model, relative_time_label(session.updated_at))
    return table


def render_files_list(paths: list[str]) -> Table:
    table = Table(title="Project files", box=box.ROUNDED)
    table.add_column("Path", style="cyan")
    for path in paths:
        table.add_row(path)
    return table


def render_footer(model: str, workspace_root: str, session: SessionRecord | None = None) -> Panel:
    left = Text()
    left.append("Local", style="bold green")
    left.append(" · ")
    left.append("Ollama", style="bold cyan")
    left.append(" · ")
    left.append("Workspace locked", style="dim")

    right = Text()
    right.append("/help", style="bold white")
    right.append(" for commands")
    if session is not None:
        right.append(" · ")
        right.append(f"{len(session.messages)} msgs", style="dim")

    meta = Text()
    meta.append(model, style="bold cyan")
    meta.append("  ")
    meta.append(workspace_root, style="green")

    return Panel(Group(left, right, meta), box=box.ROUNDED, border_style="dim", padding=(0, 1))


def render_welcome_panel() -> Panel:
    body = Group(
        Text("Ready when you are.", style="bold white"),
        Text("Examples:", style="dim"),
        Text("  hello", style="cyan"),
        Text("  explain example.cpp", style="cyan"),
        Text("  summarize README.md", style="cyan"),
        Text("  /sessions", style="cyan"),
        Text("  /model", style="cyan"),
    )
    return Panel(body, title="Start", box=box.ROUNDED, border_style="dim", padding=(0, 1))


def _message_panel(title: str, content: str, border_style: str, markdown: bool) -> Panel:
    renderable: RenderableType = Markdown(content) if markdown else Text(content)
    return Panel(renderable, title=title, box=box.ROUNDED, border_style=border_style, padding=(0, 1))

