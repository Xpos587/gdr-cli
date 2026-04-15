# gdr-cli

[![CI](https://github.com/Xpos587/gdr-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Xpos587/gdr-cli/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Gemini Deep Research CLI — run Google's Deep Research from the terminal.
Shares authentication with [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli).

## Features

- **Deep Research** — Run Gemini's multi-source deep research investigations
- **Fallback Extraction** — Automatically extracts research reports from chat history when upstream parsing fails
- **Chat** — Interactive REPL and single-message chat with Gemini (works in non-interactive environments)
- **Session Management** — List, view, and continue past conversations
- **Model Selection** — Choose specific Gemini models, check availability and subscription tier
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
gdr research "AI safety research landscape 2026"
gdr research "quantum computing applications" --no-confirm
gdr research "Rust vs Go for systems programming" -o report.md
gdr research "long topic" --timeout 60 --poll 15
```

Research prints the chat CID immediately on start. If something goes wrong, you can open the research in the browser at `https://gemini.google.com/app/<cid>` (e.g. `https://gemini.google.com/app/1975e4a9e33a362`).

### Chat

```bash
# Interactive REPL
gdr chat

# Single message (works in scripts, pipes, Claude Code, etc.)
gdr chat "Explain the difference between TCP and UDP"

# Continue last conversation
gdr chat -c

# Continue specific conversation (with or without c_ prefix)
gdr chat -c <chat-id>
```

### Session Management

```bash
# List recent chats
gdr chats list

# View conversation history
gdr chats show <chat-id>

# Limit turns displayed
gdr chats show <chat-id> -n 10
```

Chat IDs are displayed without the `c_` prefix (e.g. `1975e4a9e33a362`). This is the same ID used in Gemini web URLs: `https://gemini.google.com/app/1975e4a9e33a362`. The `c_` prefix is added automatically when needed for API calls.

### Models

```bash
gdr models
```

Lists available Gemini models, shows which are accessible for your account, and detects your subscription tier (free, plus, advanced). Probing uses metadata requests only — no inference, no limit consumption.

### Doctor

```bash
gdr doctor
```

Checks auth, cookies, Gemini connectivity, subscription tier, and Deep Research availability.

## Commands

| Command | Description |
|---------|-------------|
| `gdr research <query>` | Run Deep Research on a topic |
| `gdr chat [prompt]` | Interactive chat REPL or single message |
| `gdr chats list` | List recent chat sessions |
| `gdr chats show <cid>` | View conversation history |
| `gdr models` | List available models and subscription tier |
| `gdr login` | Authenticate via Chrome CDP |
| `gdr doctor` | Diagnose auth and connectivity |

### Global Options

- `--profile, -p` — Auth profile name (default: `default`)
- `--version, -v` — Show version
- `--debug, -d` — Enable debug logging from gemini_webapi

### Research Options

- `--timeout, -t` — Max research time in minutes (default: 30)
- `--poll` — Status polling interval in seconds (default: 10)
- `--no-confirm, -n` — Skip plan confirmation and start immediately
- `--output, -o` — Write report to file
- `--output-dir` — Auto-save to `DIR/{date}-{slug}.md`
- `--model, -m` — Model name, e.g. `gemini-3-pro-advanced` (default: auto)

### Chat Options

- `--continue, -c [CID]` — Continue a chat by ID (omit for last chat). Accepts `1975e4a9e33a362` or `c_1975e4a9e33a362`
- `--model, -m` — Model name, e.g. `gemini-3-pro-advanced` (default: auto)

- `--limit, -n` — Number of turns to display (default: 20)

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
