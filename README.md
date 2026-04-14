# gdr-cli

Gemini Deep Research CLI — run Google's Deep Research from the terminal.
Shares authentication with [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli).

## Features

- **Deep Research** — Run Gemini's multi-source deep research investigations
- **Chat** — Quick single-message chat with Gemini
- **Shared Auth** — Login once, use with both gdr and nlm
- **CDP Login** — Browser-based authentication via Chrome DevTools Protocol

## Install

```bash
uv tool install git+https://github.com/Xpos587/gdr-cli.git
```

Or from source:

```bash
git clone https://github.com/Xpos587/gdr-cli.git
cd gdr-cli
uv sync
uv run gdr --help
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Chrome/Chromium (for login)
- Gemini Advanced subscription (for Deep Research)

## Quick Start

### Login

```bash
gdr login
```

Opens Chrome for Google authentication. Cookies are saved to `~/.notebooklm-mcp-cli/profiles/default/`.

### Deep Research

```bash
# Auto-confirm plan (default)
gdr research "AI safety research landscape 2026"

# Manual plan review
gdr research "quantum computing applications" --no-confirm

# Save to file
gdr research "Rust vs Go for systems programming" -o report.md

# Custom timeout and polling
gdr research "long topic" --timeout 60 --poll 15
```

### Chat

```bash
gdr chat "Explain the difference between TCP and UDP"
```

### Doctor

```bash
gdr doctor
```

Checks auth, cookies, and Gemini connectivity.

## Commands

| Command | Description |
|---------|-------------|
| `gdr research <query>` | Run Deep Research on a topic |
| `gdr chat <prompt>` | Send a message to Gemini |
| `gdr login` | Authenticate via Chrome CDP |
| `gdr doctor` | Diagnose auth and connectivity |

### Global Options

- `--profile, -p` — Auth profile name (default: `default`)
- `--version, -v` — Show version

### Research Options

- `--timeout, -t` — Max research time in minutes (default: 30)
- `--poll` — Status polling interval in seconds (default: 10)
- `--no-confirm, -n` — Show plan and wait for manual confirmation
- `--output, -o` — Write report to file
- `--output-dir` — Auto-save to `DIR/{date}-{slug}.md`

## Auth Sharing with nlm

gdr-cli stores authentication in the same directory as notebooklm-mcp-cli:

```
~/.notebooklm-mcp-cli/
├── profiles/
│   └── default/
│       ├── cookies.json
│       └── metadata.json
└── gdr-config.json
```

Login once with either tool, both can use the same Google cookies.

## License

MIT
