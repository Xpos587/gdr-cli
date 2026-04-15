# GDR CLI — Workflow Sequences

End-to-end task sequences for common operations.

## Workflow 1: First-Time Setup

### Goal: Authenticate, verify, and run first research

```bash
# Step 1: Authenticate (opens Chrome)
gdr login

# Step 2: Verify everything works
gdr doctor
# Expected: OK for profile, cookies, connectivity, tier

# Step 3: Check available models
gdr models
# Expected: Table with available models and detected tier

# Step 4: Run first research
gdr research "AI safety research landscape 2026"
# Shows plan, asks for confirmation (Press Enter to start)
# Prints CID: https://gemini.google.com/app/<cid>
# Waits for completion, prints report

# Step 5: Save report to file
gdr research "topic" -o report.md
```

---

## Workflow 2: Deep Research Pipeline

### Goal: Run research, save report, track in browser

```bash
# Step 1: Quick research with auto-save
gdr research "quantum computing applications 2026" --output-dir ./reports/
# Creates: ./reports/2026-04-15-quantum-computing-applications-2026.md

# Step 2: Research with specific model and longer timeout
gdr research "comprehensive topic" -t 60 -m gemini-3-pro-advanced -o report.md

# Step 3: Skip confirmation for scripted use
gdr research "quick topic" -n -o quick-report.md

# Step 4: Track progress in browser (if CLI is slow)
# CID is printed immediately: https://gemini.google.com/app/<cid>
# Open in browser to see real-time progress

# Step 5: Handle failures
# If research fails, check the CID in browser for partial results
# Retry with longer timeout: gdr research "topic" -t 60
```

---

## Workflow 3: Chat Workflow

### Goal: Single message, interactive REPL, conversation continuation

```bash
# Step 1: Single message (non-interactive)
gdr chat "Explain the difference between TCP and UDP"
# Prints response and exits

# Step 2: Interactive REPL
gdr chat
# Type messages, press Enter to send
# /help — show commands
# /cid — show current chat ID
# /quit — exit

# Step 3: REPL with specific model
gdr chat -m gemini-3-flash

# Step 4: Continue last conversation
gdr chat -c
# Resumes most recent chat

# Step 5: Continue specific conversation
gdr chats list
# Find CID from list
gdr chat -c 1975e4a9e33a362
# Or with follow-up message:
gdr chat -c 1975e4a9e33a362 "Can you elaborate on point 2?"
```

---

## Workflow 4: Session Management

### Goal: Find, review, and continue past conversations

```bash
# Step 1: List recent chats
gdr chats list
# Shows: #, Title, CID, Date
# Note: CIDs displayed without c_ prefix

# Step 2: View conversation history
gdr chats show 1975e4a9e33a362
# Shows all turns (default: 20)

# Step 3: Limit displayed turns
gdr chats show 1975e4a9e33a362 -n 5
# Shows only last 5 turns

# Step 4: Continue a past conversation
gdr chat -c 1975e4a9e33a362
# Opens REPL in context of that conversation

# Step 5: Open in browser
# https://gemini.google.com/app/1975e4a9e33a362
```

---

## Workflow 5: Multi-Profile Setup

### Goal: Use multiple Google accounts

```bash
# Step 1: Authenticate primary account
gdr login                    # Default profile
gdr doctor                   # Verify

# Step 2: Authenticate secondary account
gdr login -p work            # Named profile
gdr doctor -p work           # Verify

# Step 3: Use specific profile
gdr research "topic" -p work
gdr chat "question" -p work
gdr models -p work

# Step 4: Switch between accounts
gdr research "personal topic"          # Uses default profile
gdr research "work topic" -p work      # Uses work profile
```

**Profile storage:**
```
~/.notebooklm-mcp-cli/profiles/
├── default/
│   ├── cookies.json
│   └── metadata.json
└── work/
    ├── cookies.json
    └── metadata.json
```

---

## Workflow 6: Scripting Patterns

### Error Handling in Scripts

```bash
#!/bin/bash
# Run research with error handling

gdr research "$1" -n -o output.md
exit_code=$?

case $exit_code in
    0) echo "Success" ;;
    2) echo "Auth error — run gdr login" ;;
    3) echo "Usage limit — wait and retry" ;;
    130) echo "Interrupted" ;;
    *) echo "Unknown error (exit $exit_code)" ;;
esac
```

### Batch Research

```bash
#!/bin/bash
# Research multiple topics with delays

topics=("topic 1" "topic 2" "topic 3")

for topic in "${topics[@]}"; do
    slug=$(echo "$topic" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | cut -c1-60)
    gdr research "$topic" -n -o "reports/${slug}.md" -t 30
    echo "Completed: $topic"
    sleep 60  # Delay between requests to avoid rate limits
done
```

### Check Before Running

```bash
#!/bin/bash
# Verify auth before research

if ! gdr doctor 2>/dev/null; then
    echo "Auth issue — re-logging in..."
    gdr login
fi

gdr research "topic" -o report.md
```

### Research with Timeout Fallback

```bash
#!/bin/bash
# Try short timeout first, retry with longer timeout

gdr research "$1" -t 15 -n -o report.md
if [ $? -eq 1 ] && grep -q "INCOMPLETE" report.md 2>/dev/null; then
    echo "Incomplete — retrying with longer timeout..."
    gdr research "$1" -t 60 -n -o report.md
fi
```

---

## Common Patterns

### Pattern: Re-authenticate on Failure

```bash
gdr research "topic" || (gdr login && gdr research "topic")
```

### Pattern: Capture CID for Browser Tracking

```bash
# Research in background, track in browser
gdr research "long topic" -t 60 -n 2>&1 | tee research.log
cid=$(grep -oP 'app/\K[0-9a-f]+' research.log)
echo "Track at: https://gemini.google.com/app/$cid"
```

### Pattern: Auto-Save All Research

```bash
mkdir -p ~/research-reports
gdr research "$1" --output-dir ~/research-reports/ -n
```
