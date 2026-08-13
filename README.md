DAEDALUS
========

Daedalus is a small local-first AI CLI for working inside developer projects.

What it does
------------

- talks to local Ollama models
- keeps chat sessions on disk
- reads files only from the active workspace
- lists project files and trees
- accepts simple slash commands

Requirements
------------

- Python 3.12+
- Ollama running locally

Install
-------

```bash
ollama pull gemma3:4b
uv sync
uv run daedalus
```

Or install it for direct use:

```bash
pipx install .
daedalus
```

Run it from the directory you want Daedalus to inspect.

```bash
cd ~/projects/my-app
daedalus
```

If you want to force a workspace path, set `DAEDALUS_WORKSPACE` before launch.

Commands
--------

```text
/help                  show commands
/pwd                   show workspace root
/files [path]          list files in the workspace or a subdirectory
/tree [path]           show a tree for the workspace or a subdirectory
/sessions [id]        browse or resume saved sessions
/new                   start a new session
/clear                 clear the current session
/title [name]          show or set the session title
/model                 choose a model
/exit                  quit
```

Notes
-----

Type plain English when you want chat or file help, for example:

```text
explain example.cpp
what files are in this project?
```

Daedalus will only look at files inside the workspace.