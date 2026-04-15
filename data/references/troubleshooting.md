# GDR CLI — Troubleshooting Guide

Solutions for common issues when using the `gdr` CLI.

## Quick Diagnosis

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Profile directory not found" | Never authenticated | `gdr login` |
| "Could not load profile" | Corrupt cookies | `gdr login` |
| "Cookies have expired" | Session timeout | `gdr login` |
| "Deep Research usage limit exceeded" | Daily/weekly DR limit | Wait, check subscription |
| "IP temporarily blocked by Google (429)" | Rate limit / IP block | Wait few minutes, switch network |
| "Chat not found" | Invalid CID | `gdr chats list` |
| "No report text returned" | Research incomplete | Check CID in browser, retry |
| Research hangs / no progress | Usage limit hit silently | Ctrl+C, check CID in browser |
| `gdr models` shows all "No" | Wrong tier / free account | Check subscription status |
| Chrome doesn't open on login | Port conflict / no Chrome | See Browser Issues |

---

## Authentication Issues

### Profile Not Found

**Symptoms:**
```
FAIL Profile directory not found: ~/.notebooklm-mcp-cli/profiles/default/
Run gdr login first to authenticate.
```

**Cause:** No authentication profile exists.

**Solution:**
```bash
gdr login
```

### Cookies Expired

**Symptoms:**
```
FAIL Could not load profile: Cookies have expired
```

**Cause:** Google cookies expire after a period of inactivity.

**Solution:**
```bash
gdr login
```

**Prevention:** Re-authenticate periodically. Check with `gdr doctor`.

### Missing Required Cookies

**Symptoms:**
```
WARN Missing cookies: {'__Secure-1PSIDTS'}
```

**Cause:** Partial cookie extraction during login.

**Solution:**
```bash
gdr login
```

### Account Mismatch

**Symptoms:**
```
AccountMismatchError: Cookies belong to different account
```

**Cause:** Cookies in profile were extracted from a different Google account than what's recorded in metadata.

**Solution:**
```bash
gdr login    # Re-authenticate to refresh cookies
```

---

## Browser Issues

### Chrome Doesn't Launch

**Symptoms:** `gdr login` hangs with no browser window.

**Cause:** Chrome not installed, already running, or port conflict.

**Solution:**
1. Ensure Chrome/Chromium is installed:
   ```bash
   which google-chrome || which chromium
   ```
2. Close existing Chrome instances:
   ```bash
   pkill -f chrome
   ```
3. Try manual connection (if Chrome is already running with remote debugging):
   ```bash
   gdr login --no-launch
   ```

### Port Conflict

**Symptoms:** `gdr login` fails to connect to CDP endpoint.

**Cause:** Port 9222 already in use.

**Solution:**
```bash
lsof -i :9222
kill -9 <PID>
gdr login
```

Or use a different CDP endpoint:
```bash
gdr login --cdp-url http://127.0.0.1:9333
```

---

## Network Issues

### IP Temporarily Blocked (429)

**Symptoms:**
```
Error: IP temporarily blocked by Google (429).
Try again in a few minutes, use a different proxy, or switch networks.
```

**Cause:** Too many requests from same IP address.

**Solution:**
1. Wait 5-10 minutes
2. Switch network (e.g. mobile hotspot)
3. Use a proxy/VPN
4. Retry: `gdr research "topic"`

**Prevention:** Space out research requests. Don't run multiple deep research tasks in parallel from same IP.

### Connection Timeout

**Symptoms:** Command hangs, then fails with timeout error.

**Cause:** Network connectivity issue or Gemini service degradation.

**Solution:**
1. Check network: `curl -I https://gemini.google.com`
2. Retry with longer timeout: `gdr research "topic" -t 60`
3. Check `gdr doctor` for connectivity status

---

## Usage Limit Issues

### Deep Research Limit Exceeded

**Symptoms:**
```
Error: Deep Research usage limit exceeded.
Wait a while or check your Gemini Advanced subscription.
```

**Cause:** Daily or weekly Deep Research quota exhausted.

**Exit code:** 3

**Solution:**
1. Wait (limits reset daily/weekly depending on subscription)
2. Check subscription tier: `gdr models`
3. Upgrade to Gemini Advanced for higher limits

### Research Hangs / No Progress

**Symptoms:** Research starts but spinner shows no progress for extended period.

**Cause:** Research hit a silent usage limit or the query is very complex.

**Solution:**
1. Note the CID printed at start
2. Ctrl+C to stop the CLI
3. Check progress in browser: `https://gemini.google.com/app/<cid>`
4. If report is there, extract manually or wait for limit reset

### No Report Text Returned

**Symptoms:**
```
Status: INCOMPLETE
(No report text returned)
```

**Cause:** Research didn't complete within timeout or hit a limit.

**Solution:**
1. Check CID in browser for partial results
2. Retry with longer timeout: `gdr research "topic" -t 60`
3. Wait for usage limit reset

---

## Research Issues

### Plan Parsing Failure (Fallback)

**Symptoms:** Research starts but shows warning about fallback extraction.

**Cause:** `gemini_webapi`'s plan parsing doesn't match current Gemini response format.

**Behavior:** gdr automatically falls back to polling chat history and extracting the report. This is handled transparently.

**If fallback also fails:**
1. Check CID in browser: `https://gemini.google.com/app/<cid>`
2. Copy report manually from browser
3. Report the issue on GitHub

### Research Incomplete

**Symptoms:** Report ends abruptly or status shows INCOMPLETE.

**Cause:** Timeout reached before research completed.

**Solution:**
```bash
gdr research "topic" -t 60    # Increase timeout to 60 minutes
```

---

## Chat Issues

### Chat Not Found

**Symptoms:**
```
Chat not found: 1975e4a9e33a362
```

**Cause:** Invalid or expired chat ID.

**Solution:**
```bash
gdr chats list    # Find correct CID
```

### CID Format Confusion

**Symptoms:** Commands fail with CID-related errors.

**Cause:** Mixing `c_` prefixed and non-prefixed formats incorrectly.

**Remember:**
- Display format: `1975e4a9e33a362` (no prefix)
- Browser URL: `https://gemini.google.com/app/1975e4a9e33a362`
- Input accepts BOTH: `gdr chat -c 1975e4a9e33a362` and `gdr chat -c c_1975e4a9e33a362`

### REPL Unresponsive

**Symptoms:** Chat REPL doesn't respond to input.

**Cause:** Gemini API timeout or network issue.

**Solution:**
1. Ctrl+C to interrupt
2. Check connectivity: `gdr doctor`
3. Restart REPL: `gdr chat`

---

## Model Issues

### Model Not Available

**Symptoms:** Error when using `--model` flag.

**Cause:** Selected model not available for your subscription tier.

**Solution:**
```bash
gdr models    # See which models are available for your account
```

### All Models Show "No"

**Symptoms:** `gdr models` shows all models as unavailable.

**Cause:** Auth issue or free account without model access.

**Solution:**
1. `gdr doctor` — check connectivity
2. `gdr login` — re-authenticate
3. Verify Google account has Gemini access
