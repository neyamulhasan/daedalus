from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from typing import Iterable


SUPPORTED_EXTENSIONS = {
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".go",
    ".rs",
    ".php",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".md",
    ".txt",
    ".toml",
    ".ini",
    ".sh",
}

IGNORED_DIRECTORIES = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache"}


@dataclass(slots=True)
class Workspace:
    root: Path
    max_file_bytes: int = 200_000

    def __post_init__(self) -> None:
        self.root = self.root.expanduser().resolve()

    def contains(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.root)
            return True
        except ValueError:
            return False

    def resolve_reference(self, reference: str) -> Path | None:
        cleaned = reference.strip().strip('"').strip("'")
        if not cleaned:
            return None

        candidate = Path(cleaned).expanduser()
        if not candidate.is_absolute():
            direct = (self.root / candidate).resolve()
            if direct.exists() and direct.is_file() and self.contains(direct):
                return direct
        elif candidate.exists() and candidate.is_file() and self.contains(candidate):
            return candidate.resolve()

        if "/" in cleaned or "\\" in cleaned:
            return None

        matches: list[Path] = []
        for path in self.root.rglob(cleaned):
            if path.is_file() and self.contains(path):
                matches.append(path.resolve())
                if len(matches) > 1:
                    break

        if len(matches) == 1:
            return matches[0]
        return None

    def is_supported_file(self, path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_EXTENSIONS

    def read_text_file(self, path: Path) -> str:
        resolved = path.resolve()
        if not self.contains(resolved):
            raise ValueError(f"{path} is outside the workspace")
        if not resolved.is_file():
            raise FileNotFoundError(str(path))
        if not self.is_supported_file(resolved):
            raise ValueError(f"Unsupported file type: {resolved.suffix}")
        if resolved.stat().st_size > self.max_file_bytes:
            raise ValueError(f"File is too large to read safely: {resolved.name}")
        return resolved.read_text(encoding="utf-8", errors="replace")

    def relative_path(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root))

    def resolve_directory(self, reference: str) -> Path | None:
        cleaned = reference.strip().strip('"').strip("'")
        if not cleaned:
            return None

        candidate = Path(cleaned).expanduser()
        if not candidate.is_absolute():
            direct = (self.root / candidate).resolve()
            if direct.exists() and direct.is_dir() and self.contains(direct):
                return direct
        elif candidate.exists() and candidate.is_dir() and self.contains(candidate):
            return candidate.resolve()

        if "/" in cleaned or "\\" in cleaned:
            return None

        matches: list[Path] = []
        for path in self.root.rglob(cleaned):
            if path.is_dir() and self.contains(path):
                matches.append(path.resolve())
                if len(matches) > 1:
                    break

        if len(matches) == 1:
            return matches[0]
        return None

    def list_files(self, max_items: int = 200, path: Path | None = None) -> list[str]:
        results: list[str] = []
        for file_path in self._iter_files(path):
            results.append(self.relative_path(file_path))
            if len(results) >= max_items:
                break
        return results

    def tree(self, max_depth: int = 2, max_items: int = 200, path: Path | None = None) -> str:
        start_root = self.root if path is None else path.resolve()
        lines: list[str] = [str(start_root)]
        count = 0
        for file_path in self._iter_files(path):
            rel = file_path.relative_to(start_root)
            if len(rel.parts) - 1 > max_depth:
                continue
            indent = "  " * (len(rel.parts) - 1)
            lines.append(f"{indent}- {rel.name if len(rel.parts) == 1 else rel}")
            count += 1
            if count >= max_items:
                lines.append("  ...")
                break
        return "\n".join(lines)

    def _iter_files(self, path: Path | None = None) -> Iterable[Path]:
        start_root = self.root if path is None else path.resolve()
        for root, dirnames, filenames in os.walk(start_root):
            dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRECTORIES and not name.startswith(".")]
            current_root = Path(root)
            for filename in filenames:
                path = current_root / filename
                if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file():
                    yield path


_FILE_PATTERN = re.compile(
    r"(?<!\w)([A-Za-z0-9_./\\-]+\.(?:c|cpp|h|hpp|py|js|ts|java|go|rs|php|html|css|json|ya?ml|xml|md|txt|toml|ini|sh))(?!\w)",
    re.IGNORECASE,
)


def extract_file_references(text: str) -> list[str]:
    seen: list[str] = []
    for match in _FILE_PATTERN.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def looks_like_project_question(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "what files are in this project",
            "what does this project contain",
            "what is in this project",
            "list files",
            "show files",
            "show tree",
            "tree of the project",
        )
    )


def looks_like_file_request(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("explain ", "summarize ", "analyse ", "analyze ", "compare ", "inspect ")) or bool(
        extract_file_references(text)
    )

