from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .messages import ChatMessage
from .ollama import OllamaModel
from .sessions import SessionRecord, relative_time_label


ASCII_BANNER = """\
  ██████╗  █████╗ ███████╗██████╗  █████╗ ██╗     ██╗   ██╗███████╗
  ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██║     ██║   ██║██╔════╝
  ██║  ██║███████║█████╗  ██║  ██║███████║██║     ██║   ██║███████╗
  ██║  ██║██╔══██║██╔══╝  ██║  ██║██╔══██║██║     ██║   ██║╚════██║
  ██████╔╝██║  ██║███████╗██████╔╝██║  ██║███████╗╚██████╔╝███████║
  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝"""


@dataclass(slots=True)
class Theme:
    name: str
    banner_colors: list[str]
    subtitle: str
    model_accent: str
    project_accent: str
    stats_label: str
    stats_value: str
    status_dot: str
    status_text: str
    border: str
    signature: str


THEMES = {
    "synthwave": Theme(
        name="Synthwave",
        banner_colors=["#00ffff", "#00eeff", "#00ddff", "#00ccff", "#00bbff", "#00aaff"],
        subtitle="bold magenta",
        model_accent="bold cyan",
        project_accent="bold cyan",
        stats_label="dim white",
        stats_value="bold yellow",
        status_dot="bold green",
        status_text="bold white",
        border="bold cyan",
        signature="bold yellow",
    ),
    "matrix": Theme(
        name="Matrix",
        banner_colors=["#00ff00", "#00ee00", "#00dd00", "#00cc00", "#00bb00", "#00aa00"],
        subtitle="bold green",
        model_accent="bold green",
        project_accent="bold green",
        stats_label="dim green",
        stats_value="bold bright_green",
        status_dot="bold bright_green",
        status_text="bold green",
        border="bold green",
        signature="bold bright_green",
    ),
    "dracula": Theme(
        name="Dracula",
        banner_colors=["#bd93f9", "#ff79c6", "#8be9fd", "#bd93f9", "#ff79c6", "#8be9fd"],
        subtitle="bold #ff79c6",
        model_accent="bold #8be9fd",
        project_accent="bold #bd93f9",
        stats_label="dim white",
        stats_value="bold #f1fa8c",
        status_dot="bold #50fa7b",
        status_text="bold white",
        border="bold #6272a4",
        signature="bold #ffb86c",
    ),
    "monochrome": Theme(
        name="Monochrome",
        banner_colors=["white", "white", "gray", "gray", "dark_gray", "dark_gray"],
        subtitle="bold white",
        model_accent="bold white",
        project_accent="bold white",
        stats_label="dim white",
        stats_value="bold white",
        status_dot="bold white",
        status_text="white",
        border="dim white",
        signature="bold white",
    ),
    "ocean": Theme(
        name="Ocean",
        banner_colors=["#000080", "#0000ff", "#0080ff", "#00ffff", "#80ffff", "#e0ffff"],
        subtitle="bold #00ffff",
        model_accent="bold #0080ff",
        project_accent="bold #00ffff",
        stats_label="dim #80ffff",
        stats_value="bold white",
        status_dot="bold #00ffff",
        status_text="bold white",
        border="bold #0000ff",
        signature="bold #80ffff",
    ),
    "cyberpunk": Theme(
        name="Cyberpunk",
        banner_colors=["#fcee09", "#ff003c", "#00ffff", "#ff003c", "#fcee09", "#00ffff"],
        subtitle="bold #fcee09",
        model_accent="bold #00ffff",
        project_accent="bold #ff003c",
        stats_label="dim white",
        stats_value="bold #fcee09",
        status_dot="bold #00ffff",
        status_text="bold white",
        border="bold #ff003c",
        signature="bold #00ffff",
    ),
    "retro": Theme(
        name="Retro",
        banner_colors=["#d95b43", "#c02942", "#542437", "#53777a", "#ecd078", "#d95b43"],
        subtitle="bold #ecd078",
        model_accent="bold #53777a",
        project_accent="bold #d95b43",
        stats_label="dim white",
        stats_value="bold #ecd078",
        status_dot="bold #c02942",
        status_text="bold white",
        border="bold #542437",
        signature="bold #d95b43",
    ),
}


def render_header(workspace_root: Path, model: str, session: SessionRecord | None, file_count: int, theme_id: str = "synthwave") -> RenderableType:
    theme = THEMES.get(theme_id, THEMES["synthwave"])
    banner_text = Text()
    lines = ASCII_BANNER.split("\n")
    for i, line in enumerate(lines):
        color = theme.banner_colors[min(i, len(theme.banner_colors) - 1)]
        banner_text.append(line, style=f"bold {color}")
        if i < len(lines) - 1:
            banner_text.append("\n")

    subtitle = Text("─── LOCAL AI ENGINEERING ASSISTANT ───", style=theme.subtitle)

    # Row 1: Model and Location
    row1 = Table.grid(expand=True)
    row1.add_column(justify="left")
    row1.add_column(justify="right")
    model_text = Text.assemble(("⚕ ", theme.status_dot), (model, theme.model_accent))
    row1.add_row(model_text, Text("Ollama · LOCAL", style=theme.subtitle))

    # Row 3/4: Project name and path
    project_name = f"{workspace_root.name.upper()} PROJECT"
    try:
        rel_path = f"~/{workspace_root.relative_to(Path.home())}"
    except ValueError:
        rel_path = str(workspace_root)

    row3 = Text(project_name, style=theme.project_accent)
    row4 = Text(rel_path, style="dim cyan")

    # Row 6/7: Session and stats
    stats_table = Table.grid(padding=(0, 2))
    stats_table.add_column(style=theme.stats_label, width=11)
    stats_table.add_column(style=theme.stats_value, width=25)
    stats_table.add_column(style=theme.stats_label, width=11)
    stats_table.add_column(style=theme.stats_value)

    session_id = session.id if session else "None"
    stats_table.add_row("Session", session_id)
    stats_table.add_row("Files", str(file_count), "Context", "128K")

    # Status row
    status = Text()
    status.append("● ", style=theme.status_dot)
    status.append("Model ready       ", style=theme.status_text)
    status.append("● ", style=theme.status_dot)
    status.append("Ollama connected       ", style=theme.status_text)
    status.append("● Run in local environment", style=theme.subtitle)

    body = Group(
        Padding(row1, (0, 1)),
        Text(""),
        Padding(row3, (0, 1)),
        Padding(row4, (0, 1)),
        Text(""),
        Padding(stats_table, (0, 1)),
        Text(""),
        Padding(status, (0, 1)),
    )

    sig = Text("[ A PROJECT BY KAZI ]", style=theme.signature)
    panel = Panel(body, box=box.ROUNDED, border_style=theme.border, expand=True, subtitle=sig, subtitle_align="right")

    return Group(
        Text(""),
        Align.center(banner_text),
        Text(""),
        Align.center(subtitle),
        Text(""),
        panel,
    )


def render_transcript(messages: list[ChatMessage], partial_assistant: str | None = None, max_messages: int | None = None) -> RenderableType:
    transcript_messages = list(messages)
    if partial_assistant is not None:
        transcript_messages.append(ChatMessage(role="assistant", content=partial_assistant))

    visible_messages = transcript_messages
    hidden_count = 0
    if max_messages is not None and max_messages > 0 and len(transcript_messages) > max_messages:
        hidden_count = len(transcript_messages) - max_messages
        visible_messages = transcript_messages[-max_messages:]

    blocks: list[RenderableType] = []
    if hidden_count > 0:
        blocks.append(_hidden_messages_panel(hidden_count))

    for message in visible_messages:
        if message.role == "user":
            blocks.append(_message_panel("You", message.content, "yellow", markdown=False))
        elif message.role == "assistant":
            blocks.append(_message_panel("Daedalus", message.content, "cyan", markdown=True))

    if not blocks:
        return render_welcome_panel()
    return Group(*blocks)


def render_conversation_box(
    messages: list[ChatMessage],
    partial_assistant: str | None = None,
    max_messages: int | None = None,
) -> Panel:
    transcript_messages = list(messages)
    if partial_assistant is not None:
        transcript_messages.append(ChatMessage(role="assistant", content=partial_assistant))

    visible_messages = transcript_messages
    hidden_count = 0
    if max_messages is not None and max_messages > 0 and len(transcript_messages) > max_messages:
        hidden_count = len(transcript_messages) - max_messages
        visible_messages = transcript_messages[-max_messages:]

    lines: list[RenderableType] = []
    if hidden_count > 0:
        hidden_text = "1 earlier message hidden" if hidden_count == 1 else f"{hidden_count} earlier messages hidden"
        lines.append(Text(hidden_text, style="dim"))

    if not visible_messages:
        lines.append(Text("Ready when you are.", style="dim"))
        lines.append(Text("Type a message or /help.", style="dim"))
    else:
        for index, message in enumerate(visible_messages):
            if index > 0:
                lines.append(Text("─" * 18, style="dim"))

            if message.role == "user":
                lines.append(Text("You", style="bold yellow"))
                lines.append(Text(message.content, style="white"))
            elif message.role == "assistant":
                lines.append(Text("Daedalus", style="bold cyan"))
                lines.append(Markdown(message.content))

    return Panel(
        Group(*lines),
        title="Conversation",
        box=box.ROUNDED,
        border_style="cyan",
        padding=(1, 1),
        expand=True,
    )


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
    table.expand = True
    return table


def render_sessions_table(sessions: list[SessionRecord]) -> Table:
    table = Table(title="Recent sessions", box=box.ROUNDED, show_lines=False)
    table.add_column("#", justify="right", width=4)
    table.add_column("Title", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Last Active", style="dim")

    for index, session in enumerate(sessions, start=1):
        table.add_row(str(index), session.title, session.model, relative_time_label(session.updated_at))
    table.expand = True
    return table


def render_themes_table(themes: dict[str, Theme], current_theme: str) -> Table:
    table = Table(title="Available Themes", box=box.ROUNDED, show_lines=False)
    table.add_column("#", width=4, justify="right")
    table.add_column("Current", width=8)
    table.add_column("Theme", style="cyan")

    for index, (theme_id, theme) in enumerate(themes.items(), start=1):
        marker = "●" if theme_id == current_theme else ""
        table.add_row(str(index), marker, theme.name)
    table.expand = True
    return table


def render_help_panel() -> Panel:
    body = Group(
        Text("Available Commands", style="bold white"),
        Text("", style="dim"),
        Text("Session", style="bold cyan"),
        Text("  /new                 Start a new session", style="white"),
        Text("  /sessions            Browse and resume sessions", style="white"),
        Text("  /clear               Clear the current session", style="white"),
        Text("  /title [name]        Show or set the session title", style="white"),
        Text("", style="dim"),
        Text("Workspace", style="bold cyan"),
        Text("  /pwd                 Show the current workspace root", style="white"),
        Text("  /files [path]        List files in the workspace or a subdirectory", style="white"),
        Text("  /tree [path]         Show a tree for the workspace or a subdirectory", style="white"),
        Text("", style="dim"),
        Text("Preferences", style="bold cyan"),
        Text("  /model               Choose an AI model", style="white"),
        Text("  /theme               Choose a color theme", style="white"),
        Text("", style="dim"),
        Text("General", style="bold cyan"),
        Text("  /help                Show this command list", style="white"),
        Text("  /redraw              Repaint the header banner", style="white"),
        Text("  /exit                Quit Daedalus", style="white"),
    )
    return Panel(body, title="(^_^)? Available Commands", box=box.ROUNDED, border_style="magenta", padding=(0, 1), expand=True)


def render_files_list(paths: list[str]) -> Table:
    table = Table(title="Project files", box=box.ROUNDED)
    table.add_column("Path", style="cyan")
    for path in paths:
        table.add_row(path)
    table.expand = True
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

    return Panel(Group(left, right, meta), box=box.ROUNDED, border_style="dim", padding=(0, 1), expand=True)


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
    return Panel(body, title="Start", box=box.ROUNDED, border_style="dim", padding=(0, 1), expand=True)


def _message_panel(title: str, content: str, border_style: str, markdown: bool) -> Panel:
    renderable: RenderableType = Markdown(content) if markdown else Text(content)
    return Panel(renderable, title=title, box=box.ROUNDED, border_style=border_style, padding=(0, 1), expand=True)


def _hidden_messages_panel(hidden_count: int) -> Panel:
    message = "1 earlier message hidden" if hidden_count == 1 else f"{hidden_count} earlier messages hidden"
    return Panel(Text(message, style="dim"), box=box.ROUNDED, border_style="dim", padding=(0, 1), expand=True)

