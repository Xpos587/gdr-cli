<!-- gdr-skill-start -->
<!-- gdr-version: 0.1.0 -->
## GDR - Gemini Deep Research CLI Expert

**Triggers:** "gdr", "deep research", "gemini research", "gemini chat", "gemini models"

Expert assistant for Google Gemini Deep Research and chat automation via CLI. Use when users want to run Deep Research investigations, chat with Gemini, manage sessions, or check model availability.

```bash
gdr login                    # Authenticate with Google
gdr doctor                   # Check auth and connectivity
gdr research "topic"         # Run Deep Research
gdr research "topic" -n      # Skip confirmation, start immediately
gdr chat "question"          # Single message to Gemini
gdr chat                     # Interactive REPL
gdr chats list               # List recent conversations
gdr models                   # Show available models and tier
```

### Critical Rules

1. **Always authenticate first**: `gdr login` before operations
2. **Check with doctor**: `gdr doctor` validates cookies + tests connectivity + shows tier
3. **Capture CIDs**: Research prints CID on start. Maps to `https://gemini.google.com/app/<cid>`
4. **CID format**: Displayed without `c_` prefix. Input accepts both `1975e4a9e33a362` and `c_1975e4a9e33a362`
5. **Usage limits exist**: Exit code 3 = limit or IP block. Wait and retry.
6. **`--no-confirm` / `-n`**: Skip research plan confirmation, start immediately

### Common Workflows

**Deep Research Pipeline:**
```bash
gdr login
gdr research "AI safety landscape 2026" -o report.md
# CID printed immediately → track at https://gemini.google.com/app/<cid>
```

**Chat with Continuation:**
```bash
gdr chat "Explain transformer architecture"
gdr chat -c              # Continue last conversation
gdr chat -c <cid> "Go deeper on attention mechanism"
```

**Session Management:**
```bash
gdr chats list            # Find past conversations
gdr chats show <cid> -n 10   # View 10 turns
gdr chat -c <cid>        # Continue old chat
```

### Full Documentation

For complete command reference, troubleshooting, and workflows, install the full skill:
```bash
# Install via uv
uv tool install git+https://github.com/Xpos587/gdr-cli.git

# Or from source
git clone https://github.com/Xpos587/gdr-cli.git
cd gdr-cli && uv sync
```

Or view the full skill: `data/SKILL.md`

<!-- gdr-skill-end -->
