# GDR CLI — Complete Command Reference

All commands, flags, and options for the `gdr` CLI.

## Table of Contents

1. [Global Options](#global-options)
2. [Authentication](#authentication)
3. [Doctor](#doctor)
4. [Deep Research](#deep-research)
5. [Chat](#chat)
6. [Session Management](#session-management)
7. [Models](#models)

---

## Global Options

```bash
gdr --version, -v      # Show version and exit
gdr --debug, -d        # Enable debug logging from gemini_webapi
gdr --help             # Show help and exit
```

| Option | Short | Description |
|--------|-------|-------------|
| `--version` | `-v` | Show version and exit |
| `--debug` | `-d` | Enable debug logging from gemini_webapi |

---

## Authentication

### gdr login

Authenticate with Google via Chrome DevTools Protocol. Stores cookies in `~/.notebooklm-mcp-cli/profiles/` (shared with nlm).

```bash
gdr login [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--profile` | `-p` | Auth profile name (shared with nlm) (default: `default`) |
| `--cdp-url` | | Chrome CDP endpoint (default: `http://127.0.0.1:9222`) |
| `--launch` / `--no-launch` | `-l` | Auto-launch Chrome if CDP not reachable (default: `--launch`) |

**Examples:**
```bash
gdr login                          # Default: launch Chrome, extract cookies
gdr login -p work                  # Named profile for separate account
gdr login --no-launch              # Connect to already-running Chrome
gdr login --cdp-url http://127.0.0.1:9333  # Custom CDP endpoint
```

**Output:** Cookie count, email address, profile name.

---

## Doctor

### gdr doctor

Diagnose auth, cookies, metadata, and Gemini connectivity.

```bash
gdr doctor [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--profile` | `-p` | Auth profile to check (default: `default`) |

**Checks performed:**
1. Profile directory exists
2. Cookies file exists and loads
3. Required cookies present (`__Secure-1PSID`, `__Secure-1PSIDTS`)
4. Metadata (email, last validated timestamp)
5. Gemini connectivity (authenticated and accessible)
6. Subscription tier (`free`, `plus`, `advanced`)
7. Deep Research availability

**Examples:**
```bash
gdr doctor              # Full diagnostic
gdr doctor -p work      # Check specific profile
```

---

## Deep Research

### gdr research

Run Gemini Deep Research on a topic. Prints chat CID immediately on start for browser tracking.

```bash
gdr research [OPTIONS] QUERY
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `QUERY` | | | Research topic or question (required) |
| `--profile` | `-p` | `default` | Auth profile name |
| `--timeout` | `-t` | `30` | Max research time in minutes |
| `--poll` | | `10.0` | Status polling interval in seconds |
| `--no-confirm` | `-n` | | Skip plan confirmation, start immediately |
| `--output` | `-o` | | Write report to file |
| `--output-dir` | | | Auto-save to `DIR/{date}-{slug}.md` |
| `--model` | `-m` | | Model name (default: auto) |

**Examples:**
```bash
gdr research "AI safety research landscape 2026"
gdr research "quantum computing applications" --no-confirm
gdr research "Rust vs Go for systems programming" -o report.md
gdr research "long topic" --timeout 60 --poll 15
gdr research "topic" --output-dir ./reports/
gdr research "topic" -m gemini-3-pro-advanced
```

**CID tracking:** Research prints `Chat: https://gemini.google.com/app/<cid>` immediately. Use this URL to track progress in browser if CLI output is interrupted.

**Fallback extraction:** If upstream plan parsing fails, gdr automatically polls chat history and extracts the completed report. No manual intervention needed.

**Output file format:**
```markdown
# Deep Research Report

> Query: <query>
> Status: COMPLETED
> Title: <plan title>

<report text>
```

---

## Chat

### gdr chat

Chat with Gemini. No prompt enters interactive REPL mode.

```bash
gdr chat [OPTIONS] [PROMPT]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `PROMPT` | | | Message to send to Gemini (optional) |
| `--profile` | `-p` | `default` | Auth profile name |
| `--continue` | `-c` | | Continue chat by CID (omit for last chat) |
| `--model` | `-m` | | Model name (default: auto) |

**Examples:**
```bash
gdr chat                                    # Interactive REPL
gdr chat "Explain TCP vs UDP"               # Single message
gdr chat -c                                 # Continue last conversation
gdr chat -c 1975e4a9e33a362                 # Continue specific chat
gdr chat -c c_1975e4a9e33a362               # With c_ prefix (also works)
gdr chat -c <cid> "follow-up question"      # Message in continued chat
gdr chat -m gemini-3-pro-advanced           # Specific model
gdr chat -m gemini-3-flash                  # REPL with specific model
```

**REPL commands (inside interactive mode):**
- `/help` — Show available commands
- `/quit` — Exit the REPL
- `/cid` — Show current chat ID

---

## Session Management

### gdr chats list

List recent chat conversations.

```bash
gdr chats list [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--profile` | `-p` | `default` | Auth profile name |

**Output columns:** #, Title, CID, Date

**Examples:**
```bash
gdr chats list           # List recent chats
gdr chats list -p work   # Different profile
```

### gdr chats show

Show conversation history for a chat.

```bash
gdr chats show [OPTIONS] CID
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `CID` | | | Chat ID (with or without `c_` prefix) |
| `--profile` | `-p` | `default` | Auth profile name |
| `--limit` | `-n` | `20` | Number of turns to show |

**Examples:**
```bash
gdr chats show 1975e4a9e33a362          # Show 20 turns
gdr chats show c_1975e4a9e33a362        # With c_ prefix
gdr chats show 1975e4a9e33a362 -n 10    # Limit to 10 turns
```

---

## Models

### gdr models

List available Gemini models. Probes account to check which models are available and detects subscription tier.

```bash
gdr models [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--profile` | `-p` | `default` | Auth profile name |

**Output columns:** Model Name, Advanced (requires Advanced subscription), Available

**Examples:**
```bash
gdr models           # List models and detected tier
gdr models -p work   # Different profile
```

**Note:** Model probing uses RPC metadata/config requests only — no inference, no limit consumption.
