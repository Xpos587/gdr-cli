---
name: gdr-skill
version: "0.1.0"
description: "Expert guide for the GDR CLI (`gdr`) — Gemini Deep Research and Chat from the terminal. Use this skill when users want to run Google's Deep Research, chat with Gemini, manage chat sessions, or check model availability. Triggers on mentions of \"gdr\", \"deep research\", \"gemini research\", \"gemini chat\", or any Gemini automation task."
---

# GDR CLI — Gemini Deep Research & Chat Expert

Expert assistant for Google Gemini Deep Research and chat automation via the `gdr` CLI.

## Tool Detection (CRITICAL — Read First!)

**ALWAYS check if `gdr` is available before proceeding:**

```bash
which gdr || which uv
```

If `gdr` is not found but `uv` is available, use `uv run gdr`:
```bash
uv run gdr --help
```

**Decision Logic:**
```
has_gdr = check_bash_available("which gdr")
has_uv = check_bash_available("which uv")

if has_gdr:
    use "gdr" directly
elif has_uv:
    use "uv run gdr" for all commands
else:
    ask user to install: uv tool install git+https://github.com/Xpos587/gdr-cli.git
```

## Quick Reference

```bash
gdr login                      # Authenticate with Google
gdr doctor                     # Check auth and connectivity
gdr research "topic"           # Run Deep Research
gdr research "topic" -n        # Skip confirmation, start immediately
gdr chat "question"            # Single message to Gemini
gdr chat                       # Interactive REPL
gdr chats list                 # List recent conversations
gdr models                     # Show available models and tier
```

## Critical Rules

1. **Always authenticate first**: Run `gdr login` before any operations
2. **Check auth with doctor**: `gdr doctor` validates cookies, tests connectivity, and shows subscription tier
3. **Capture CIDs from output**: Research and chat commands return chat IDs needed to continue sessions or view in browser
4. **CID format**: Displayed without `c_` prefix (e.g. `1975e4a9e33a362`), matches Gemini web URL: `https://gemini.google.com/app/<cid>`
5. **Input accepts both formats**: `--continue 1975e4a9e33a362` and `--continue c_1975e4a9e33a362` both work
6. **Usage limits exist**: Deep Research may hit `UsageLimitExceeded` — wait and retry. Exit code 3.
7. **IP blocks are transient**: `TemporarilyBlocked` (429) — wait a few minutes, try different network. Exit code 3.
8. **`--confirm` is the default**: Research asks for plan confirmation unless `--no-confirm` / `-n` is passed

## Workflow Decision Tree

```
User wants to...
│
├─► Research a topic deeply
│   └─► gdr research "query" [-n] [-t 60] [-o report.md]
│       ├─► Save to file: add --output report.md
│       ├─► Auto-save: add --output-dir ./reports/
│       └─► Longer timeout: add --timeout 60
│
├─► Chat with Gemini
│   ├─► Single question → gdr chat "question"
│   ├─► Interactive REPL → gdr chat
│   └─► Continue old chat → gdr chat -c <cid>
│
├─► Manage sessions
│   ├─► List chats → gdr chats list
│   ├─► View history → gdr chats show <cid>
│   └─► View specific turns → gdr chats show <cid> -n 10
│
├─► Check models/tier
│   └─► gdr models
│
└─► Troubleshoot auth
    └─► gdr doctor
```

## 1. Authentication

Authenticate via Chrome DevTools Protocol. Stores cookies in `~/.notebooklm-mcp-cli/profiles/` (shared with nlm).

```bash
gdr login                      # Launch Chrome, extract cookies
gdr login -p work              # Use named profile
gdr login --cdp-url http://127.0.0.1:9333  # Custom CDP endpoint
gdr login --no-launch          # Don't auto-launch Chrome
gdr doctor                     # Validate auth + check connectivity
```

**Profile paths:**
```
~/.notebooklm-mcp-cli/profiles/{name}/
├── cookies.json       # Google auth cookies
└── metadata.json      # Email, last validated timestamp
```

**Multiple accounts:** Use `--profile` / `-p` for separate Google accounts.

## 2. Deep Research

Run Google's multi-source deep research investigations.

```bash
gdr research "AI safety research landscape 2026"
gdr research "topic" -n                          # Skip confirmation
gdr research "topic" -o report.md                # Save to file
gdr research "topic" --output-dir ./reports/     # Auto-save: {date}-{slug}.md
gdr research "topic" -t 60 --poll 15             # 60min timeout, 15s poll
gdr research "topic" -m gemini-3-pro-advanced    # Specific model
```

### Research Options

| Option | Short | Description |
|--------|-------|-------------|
| `--timeout` | `-t` | Max research time in minutes (default: 30) |
| `--poll` | | Status polling interval in seconds (default: 10) |
| `--no-confirm` | `-n` | Skip plan confirmation, start immediately |
| `--output` | `-o` | Write report to specific file |
| `--output-dir` | | Auto-save to `DIR/{date}-{slug}.md` |
| `--model` | `-m` | Model name (default: auto) |
| `--profile` | `-p` | Auth profile name |

### CID Tracking

Research prints the chat CID immediately on start. If something goes wrong, open in browser:
```
https://gemini.google.com/app/<cid>
```

### Fallback Extraction

If upstream plan parsing fails, gdr automatically falls back to polling chat history and extracting the report. This handles edge cases where `gemini_webapi`'s response format changes.

## 3. Chat

Interactive REPL or single-message mode.

### Single Message
```bash
gdr chat "Explain the difference between TCP and UDP"
gdr chat "question" -m gemini-3-pro-advanced    # Specific model
```

### Interactive REPL
```bash
gdr chat                       # Start REPL
gdr chat -m gemini-3-flash     # REPL with specific model
```

**REPL Commands:**
- `/help` — Show available commands
- `/quit` — Exit the REPL
- `/cid` — Show current chat ID

### Continue Conversation
```bash
gdr chat -c                    # Continue last conversation
gdr chat -c 1975e4a9e33a362   # Continue specific chat
gdr chat -c c_1975e4a9e33a362 # Also works with c_ prefix
gdr chat -c <cid> "follow-up" # Send message in continued chat
```

### Chat Options

| Option | Short | Description |
|--------|-------|-------------|
| `--continue` | `-c` | Continue chat by CID (omit for last chat) |
| `--model` | `-m` | Model name (default: auto) |
| `--profile` | `-p` | Auth profile name |

## 4. Session Management

### List Chats
```bash
gdr chats list                 # Show recent conversations
gdr chats list -p work         # Different profile
```

### View Chat History
```bash
gdr chats show <cid>           # Show conversation (20 turns default)
gdr chats show <cid> -n 10     # Limit to 10 turns
gdr chats show c_1975e4a9e33a362  # With or without c_ prefix
```

## 5. Models

Probe account to see available models and detected subscription tier.

```bash
gdr models                     # List models with availability status
gdr models -p work             # Different profile
```

**Output columns:**
- Model Name — real model identifier (e.g. `gemini-3-pro-advanced`)
- Advanced — whether model requires Advanced subscription
- Available — whether your account can use it

**Tier detection:** `free`, `plus`, or `advanced` (inferred from RPC probes — no inference, no limit consumption).

## 6. Doctor

Diagnose auth, cookies, metadata, and Gemini connectivity.

```bash
gdr doctor                     # Full diagnostic
gdr doctor -p work             # Specific profile
```

**Checks performed:**
1. Profile directory exists
2. Cookies file exists and loads
3. Required cookies present (`__Secure-1PSID`, `__Secure-1PSIDTS`)
4. Metadata (email, last validated)
5. Gemini connectivity + subscription tier + Deep Research availability

## CID Convention

Chat IDs are **displayed without** the `c_` prefix:
```
gdr chats list
# Shows: 1975e4a9e33a362 (not c_1975e4a9e33a362)
```

This matches Gemini web URLs:
```
https://gemini.google.com/app/1975e4a9e33a362
```

All input commands accept **both formats**:
```bash
gdr chat -c 1975e4a9e33a362      # Works
gdr chat -c c_1975e4a9e33a362    # Also works
gdr chats show 1975e4a9e33a362   # Works
gdr chats show c_1975e4a9e33a362 # Also works
```

## Error Recovery

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | Success | — |
| 1 | Generic error | Check error message |
| 2 | GDRError (auth/config) | Check profile, re-login |
| 3 | Usage limit / IP block | Wait and retry |
| 130 | Interrupted (Ctrl+C) | Normal exit |

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Deep Research usage limit exceeded" | Daily/weekly DR limit hit | Wait, check subscription |
| "IP temporarily blocked by Google (429)" | Too many requests | Wait few minutes, switch network/proxy |
| "Cookies have expired" | Session timeout | `gdr login` |
| "Profile directory not found" | Never authenticated | `gdr login` |
| "Chat not found" | Invalid CID | `gdr chats list` to find correct CID |
| "No report text returned" | Research incomplete | Check CID in browser, retry with longer timeout |

## Rate Limiting

- **Deep Research**: Subject to daily/weekly usage limits depending on subscription tier
- **UsageLimitExceeded**: Wait before retrying. Higher tiers get more quota.
- **TemporarilyBlocked (429)**: IP-level block. Wait a few minutes, try different network or proxy.
- **Chat**: Lower limits than DR, but still rate-limited

**Mitigation:**
- Use `--timeout` to match expected research duration
- If blocked, wait 5-10 minutes before retry
- Switch networks or use proxy for IP blocks

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

## Advanced Reference

- **Command Reference**: See `references/command_reference.md` for complete flags and options
- **Troubleshooting**: See `references/troubleshooting.md` for detailed error resolution
- **Workflows**: See `references/workflows.md` for end-to-end task sequences
