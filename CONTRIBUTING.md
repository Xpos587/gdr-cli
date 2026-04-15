# Contributing to gdr-cli

Thanks for your interest in contributing. gdr-cli provides terminal access to Gemini's Deep Research and chat, built on top of `gemini-webapi`. The upstream API is unofficial and can change without notice, so contributions need to be grounded in verified behavior.

## Before You Start

For small features, bug fixes, and improvements, just open a PR with a clear description.

For large architectural changes (new auth providers, new command groups, streaming support), open an issue first to discuss the approach.

## Development Setup

**Requirements:** Python >= 3.12, uv, Chrome/Chromium

```bash
git clone https://github.com/Xpos587/gdr-cli.git
cd gdr-cli
uv sync

# Authenticate (opens Chrome for Google login)
uv run gdr login

# Verify
uv run gdr doctor
```

### Reinstalling After Code Changes

If you installed via `uv tool install`, rebuild and reinstall:

```bash
uv sync && uv tool install --force .
```

## Architecture

```
src/
├── cli.py         →  Typer commands (thin wrappers, UX concerns only)
├── auth.py        →  Profile/cookie management, disk I/O
├── config.py      →  Path resolution, GDRConfig
├── chat.py        →  Gemini chat sessions (send, continue, list, history, delete)
├── repl.py        →  Interactive REPL (prompt_toolkit)
├── research.py    →  Deep research orchestration (plan → confirm → poll → result, fallback chat extraction)
├── cdp.py         →  Chrome DevTools Protocol login (cookie extraction)
└── exceptions.py  →  GDRError hierarchy
```

**Layering rules:**

- `cli.py` handles UX (prompts, tables, error display) and delegates to `chat.py`, `research.py`, `auth.py`
- `cli.py` must **never** import `gemini_webapi` directly — always go through `auth.py` or `chat.py`
- Business logic lives in `chat.py` and `research.py`, not in `cli.py`
- All errors surface as `GDRError` subclasses with optional `hint` field

## How to Implement a New Feature

### 1. Add the Core Logic

| Step | File | What |
|------|------|------|
| 1 | `src/*.py` | Add the function (async where I/O is involved) |
| 2 | `src/exceptions.py` | Add a specific `GDRError` subclass if needed |
| 3 | `tests/test_*.py` | Write unit tests with mocked `gemini_webapi` |
| 4 | `src/cli.py` | Wire up a Typer command (thin wrapper) |

### 2. Test Before Wiring CLI

Validate the core function works with mocked `gemini_webapi` before adding the CLI command. Write unit tests first, confirm they pass, then add the Typer wrapper.

## Code Quality

```bash
# Tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=term-missing

# Single test
uv run pytest tests/test_chat.py::TestSendMessage -v
```

### Commit Messages

Use Conventional Commits:

- `feat:` New feature
- `fix:` Bug fix
- `style:` Formatting, lint fixes (no logic change)
- `docs:` Documentation only
- `refactor:` Code change that neither fixes a bug nor adds a feature
- `test:` Adding or updating tests

## Error Handling

- Raise `GDRError` subclasses from `exceptions.py`. Never raw Python exceptions in CLI-facing code.
- Chain exceptions: `raise GDRError(...) from err`
- `cli.py` catches `GDRError` and displays `message` + optional `hint`, exits with code 2
- Destructive operations must require confirmation (see `--no-confirm` for research)

Exit codes: 0=ok, 1=error, 2=GDRError, 3=usage limit, 130=interrupt

## Security

- **Never commit cookies, tokens, or credentials.** Not in code, tests, or examples.
- **File permissions.** Auth files use restrictive permissions (`0o600` / `0o700`) — see `auth.py`
- **No command injection.** Never pass user input to shell commands unsanitized.

To report a security vulnerability, email the maintainer directly. Don't open a public issue.

## PR Guidelines

- **One feature or fix per PR.**
- **Include a clear description.** What changed, why, and how you verified it.
- **Tests must pass.** Run `uv run pytest` before pushing.
- **Don't bump the version.** The maintainer handles versioning and releases.
- **Don't add `Co-authored-by` trailers.** Commits are attributed to the PR author.

## Dependencies

This project keeps dependencies minimal. If your change requires a new dependency, justify it in the PR description. Prefer using what's already available (`typer`, `rich`, `prompt-toolkit`, `pydantic`) over adding new packages.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
