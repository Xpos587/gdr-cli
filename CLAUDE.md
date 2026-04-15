# gdr-cli

Gemini Deep Research CLI. Run Google's Deep Research and chat with Gemini from terminal. Shares auth with [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli).

## Commands

```bash
uv run gdr --help          # CLI entrypoint
uv run pytest              # Tests (pythonpath = src/)
uv run gdr doctor          # Diagnose auth + connectivity
uv run gdr login           # Chrome CDP auth
uv run gdr research "..."  # Deep research
uv run gdr chat            # Interactive REPL
```

## Architecture

```
src/
├── cli.py         # Typer app — all CLI commands (research, chat, login, doctor, chats)
├── auth.py        # AuthManager + Profile — cookie loading, profile CRUD, account mismatch guard
├── config.py      # Path resolution + GDRConfig — ~/.notebooklm-mcp-cli/ layout
├── chat.py        # Gemini chat session management — send, continue, list, read history, delete
├── repl.py        # Interactive REPL (prompt_toolkit) — multi-turn chat with /help, /quit, /cid
├── research.py    # Deep research orchestration — plan → confirm → poll → result
├── cdp.py         # Chrome DevTools Protocol login — cookie extraction
└── exceptions.py  # GDRError, AuthError, AccountMismatchError, ProfileNotFoundError
tests/             # pytest (testpaths = tests/, pythonpath = src/)
data/              # Static data files
```

## Key Dependencies

- `gemini-webapi` — Gemini HTTP client (async). Core API: `GeminiClient`, `start_chat`, `deep_research`
- `typer` — CLI framework
- `rich` — Terminal formatting
- `prompt-toolkit` — REPL input
- `pydantic` — Config validation

## Conventions

- Auth storage: `~/.notebooklm-mcp-cli/profiles/{name}/cookies.json` + `metadata.json`
- Profile permissions: dir 0o700, files 0o600
- All modules use `from __future__ import annotations`
- Lazy imports inside CLI commands (keeps startup fast)
- Async throughout — CLI commands use `asyncio.run()`
- Errors surface as `GDRError` subclasses with optional `hint` field
- Exit codes: 0=ok, 1=error, 2=GDRError, 3=usage limit, 130=interrupt
