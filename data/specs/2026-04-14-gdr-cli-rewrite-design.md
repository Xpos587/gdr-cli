# GDR CLI Rewrite Design

## Goal

Rewrite gdr-cli with nlm-inspired architecture (auth, config, exceptions, CLI polish)
while keeping gemini_webapi as the HTTP layer. No MCP server. Four commands only:
research, chat, login, doctor. Simple sequential flow.

## Architecture

gdr-cli wraps gemini_webapi for Gemini Deep Research and chat. Auth is shared with nlm
via `~/.notebooklm-mcp-cli/profiles/`. Chrome CDP handles browser-based login. Typer + Rich
for CLI. Pydantic for models.

## Tech Stack

- Python 3.12+, uv for tooling
- gemini_webapi >= 2.0.0 (Gemini HTTP client with DR support)
- typer >= 0.15.0 (CLI framework)
- rich >= 13.0.0 (console output)
- websocket-client >= 1.0.0 (CDP)
- pydantic >= 2.0 (data models, inherited from gemini_webapi)

---

## Project Structure

```
gdr-cli/
├── src/gdr_cli/
│   ├── __init__.py          # __version__
│   ├── cli.py               # Typer app, 4 commands
│   ├── auth.py              # Profile, AuthManager, cookie loading
│   ├── config.py            # Path resolution, persistent config
│   ├── cdp.py               # CDP browser automation
│   ├── research.py          # DR flow (plan → confirm → poll → result)
│   ├── chat.py              # Simple chat wrapper
│   └── exceptions.py        # Custom exceptions with user hints
├── tests/
│   ├── test_auth.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_research.py
│   └── test_cdp.py
├── pyproject.toml
└── README.md
```

## Module Details

### exceptions.py

Custom exception hierarchy inspired by nlm. Each exception carries a `hint` for
user-facing guidance.

```
GDRError (base)
├── AuthError           # Auth failure (missing cookies, expired session)
├── ProfileNotFoundError(profile_name)
├── AccountMismatchError(stored_email, new_email)
├── ResearchError       # DR-specific (plan not created, polling failed)
├── RateLimitError      # Usage limit exceeded
└── ConnectionError     # Network/CDP issues
```

### auth.py

Adopts nlm's Profile + AuthManager pattern.

**Profile dataclass:**
- `name: str`
- `cookies: list[dict] | dict[str, str]`
- `csrf_token: str | None`
- `session_id: str | None`
- `email: str | None`
- `build_label: str | None`
- `last_validated: datetime | None`
- `to_dict()` / `from_dict()` for serialization

**AuthManager:**
- `__init__(profile_name="default")`
- `load_profile() -> Profile` — reads cookies.json + metadata.json
- `save_profile(cookies, csrf_token, session_id, email, build_label) -> Profile`
- `delete_profile()`
- `get_cookies() -> dict[str, str]` — converts list[dict] to dict
- `list_profiles() -> list[str]` — static, lists all profile dirs
- `profile_exists() -> bool`
- Account mismatch guard on save (warn if saving different email to existing profile)

Storage: `~/.notebooklm-mcp-cli/profiles/{name}/cookies.json` + `metadata.json`
Same format as nlm for full compatibility.

### config.py

Path resolution + optional persistent config file.

**Path helpers (same as current):**
- `get_base_dir() -> Path` — `~/.notebooklm-mcp-cli`
- `get_profiles_dir() -> Path`
- `get_profile_dir(profile) -> Path`
- `get_cookies_file(profile) -> Path`
- `get_metadata_file(profile) -> Path`

**Persistent config (new):**
- `get_config() -> GDRConfig`
- `GDRConfig` dataclass with defaults:
  - `default_profile: str = "default"`
  - `default_timeout: int = 30` (minutes)
  - `default_poll_interval: float = 10.0` (seconds)
  - `auto_confirm: bool = True`
  - `output_dir: Path | None = None`
- Stored at `~/.notebooklm-mcp-cli/gdr-config.json`

### cli.py

Typer app with 4 commands. Rich console on stderr.

**`gdr research <query>`**
- Options: `--profile`, `--timeout`, `--poll`, `--no-confirm`, `--output`, `--output-dir`
- Flow: load auth → create plan → show plan (with Rich formatting) → confirm/auto-confirm →
  start research → poll with live progress spinner → format result → save/print
- Rich progress: spinner with status text during polling, plan displayed as formatted card

**`gdr chat <prompt>`**
- Options: `--profile`
- Simple: load auth → send message → print response
- Error handling via custom exceptions

**`gdr login`**
- Options: `--profile`, `--cdp-url`, `--launch/--no-launch`
- CDP flow with Rich status messages
- Shows email, cookie count on success

**`gdr doctor`**
- Options: `--profile`
- Checks: profile dir exists, cookies loadable, required cookies present,
  metadata valid, Gemini connectivity, DR availability
- Rich formatted output (green OK / red FAIL / yellow WARN)

**Global options:**
- `--version / -v`
- `--profile / -p` (on all commands)

### research.py

Wraps gemini_webapi for Deep Research flow.

**`run_deep_research(query, profile, timeout_min, poll_interval, auto_confirm) -> DeepResearchResult`**
- Uses AuthManager to load cookies
- Creates GeminiClient from gemini_webapi
- Calls `create_deep_research_plan()` → displays plan → confirms →
  `start_deep_research()` → `wait_for_deep_research()` with status callback
- Status callback updates Rich Live display

**`format_result(result) -> str`**
- Rich-formatted output: title, query, status, full report text

**`format_plan(plan) -> str`**
- Rich-formatted plan display: title, steps, ETA, confirm/modify prompts

### chat.py

Simple wrapper around gemini_webapi.

**`send_message(prompt, profile, timeout) -> str`**
- Uses AuthManager to load cookies
- Creates GeminiClient, starts chat, sends message, returns text

### cdp.py

Keep as-is. Already solid implementation:
- `find_browser()`, `find_available_port()`, `get_debugger_url()`
- `launch_browser()`, `cdp_command()`, `get_all_cookies()`
- `login_via_cdp()` — full flow with cookie filtering to .google.com

---

## Data Flow

```
CLI command
  → AuthManager.load_profile()
    → ~/.notebooklm-mcp-cli/profiles/{name}/cookies.json + metadata.json
  → GeminiClient(secure_1psid, secure_1psidts) from gemini_webapi
    → Gemini API (gemini.google.com)
  → Rich console output (stderr)
```

## Shared Auth with nlm

Both tools read/write the same directory structure:
```
~/.notebooklm-mcp-cli/
├── profiles/
│   └── default/
│       ├── cookies.json     # list[dict] cookie format
│       └── metadata.json    # csrf_token, session_id, email, etc.
└── gdr-config.json          # gdr-specific settings
```

Login once with either tool, both can use the same cookies.

## Error Handling Strategy

All errors go through custom exceptions with user-facing hints:
- `AuthError("Missing __Secure-1PSID", hint="Run 'gdr login' to authenticate.")`
- `RateLimitError("Deep Research usage limit exceeded.", hint="Wait or check subscription.")`
- CLI catches exceptions and displays Rich-formatted error + hint

## Testing Strategy

- Unit tests for auth.py (Profile serialization, AuthManager load/save)
- Unit tests for config.py (path resolution, config loading)
- Unit tests for cli.py (command parsing, option validation)
- Integration tests for research.py (mocked gemini_webapi)
- Keep existing test patterns (pytest, pytest-asyncio)

## What We're NOT Building

- No MCP server (unlike nlm)
- No parallel research tasks (simple sequential flow)
- No background/daemon mode
- No streaming output (architecture is future-ready but not implemented)
- No httpx (gemini_webapi handles all HTTP)
- No NotebookLM-specific features (notebooks, sources, studio, sharing)
