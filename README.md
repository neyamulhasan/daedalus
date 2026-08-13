DAEDALUS
========

A local AI assistant that runs inside your terminal.
Talks to Ollama. Reads only your project files. Nothing leaves your machine.

* Source code: https://github.com/neyamulhasan/daedalus-cli
* Report a bug: Open an issue on GitHub
* Requirements: Python >= 3.12, Ollama running locally


What It Does
------------

* Talks to local Ollama models (e.g. gemma3:4b, llama3)
* Reads and explains files inside your current project
* Remembers chat sessions across launches
* Lists files and shows directory trees
* Lets you pick models and color themes on the fly
* All slash commands are tab-completable


Who Are You?
============

Find your role below:

* First-time user        - Read Quick Start below
* Daily developer        - Read Commands and Tips below
* Sysadmin               - Read Environment Variables and Config sections
* Contributor            - Read Development section


Quick Start
===========

Pull a model and run:

    ollama pull gemma3:4b
    uv sync
    cd ~/myproject
    uv run daedalus

Or install globally:

    pipx install .
    daedalus

That is it. Run it from the project directory you want it to read.


Commands
========

Type these at the prompt:

    /help                  show all commands
    /pwd                   show current workspace path
    /files [path]          list files in workspace or a subdirectory
    /tree  [path]          show directory tree
    /sessions [id]         browse or resume a saved session
    /manage                manage all sessions across workspaces
    /new                   start a new session
    /clear                 wipe messages in current session
    /title [name]          show or rename current session
    /model                 pick a different Ollama model
    /unload                free model from memory
    /theme                 change the color theme
    /redraw                redraw the header banner
    /exit                  quit


Launch Flags
============

    daedalus               start fresh session in current directory
    daedalus -r            resume last session
    daedalus -r 2          resume session number 2
    daedalus -s <id>       resume session by ID


Tips
====

Just type plain English. For example:

    explain app.py
    what does workspace.py do?
    what files are in the src folder?

Daedalus will only look at files inside the workspace directory.
It will not read anything outside of it.


Environment Variables
=====================

    DAEDALUS_HOME         where sessions and config are stored (default: ~/.daedalus)
    DAEDALUS_WORKSPACE    force a specific workspace root (default: current directory)


Configuration
=============

File lives at ~/.daedalus/config.toml

    host = "http://127.0.0.1:11434"   # Ollama server address
    model = "gemma3:4b"               # default model
    max_history_messages = 24         # how many past messages to include
    max_file_bytes = 200000           # skip files larger than this
    recent_session_limit = 100        # max sessions shown in the browser
    theme = "synthwave"               # color theme


Development
===========

    uv sync          install dependencies
    uv run pytest    run tests
    uv run daedalus  run from source