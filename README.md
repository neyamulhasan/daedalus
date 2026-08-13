# Daedalus

Daedalus is a lightweight, local-first AI CLI for developer projects.

## Status

This repository currently contains the V0.1 Python implementation scaffold:

- Ollama model discovery
- streamed chat over Ollama
- workspace-limited file reading
- local JSON chat sessions
- basic project inspection commands

## Install

Requires Python 3.12+ and Ollama running locally.

```bash
ollama pull gemma3:4b
uv sync
uv run daedalus
```

Or install for direct use:

```bash
pipx install .
daedalus
```

## Usage

Start Daedalus from a project directory:

```bash
cd ~/projects/my-app
daedalus
```

Commands supported in this V0.1 slice include:

- `/model`
- `/sessions`
- `/resume <number-or-session-id>`
- `/new`
- `/clear`
- `/title`
- `/pwd`
- `/files`
- `/tree`

Natural language file requests such as `explain example.cpp` and project questions like `what files are in this project?` are routed to local file context when possible.
# daedalus