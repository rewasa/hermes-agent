---
name: browser-stack
description: Browser automation tool selection — proofshot for local, camoufox for external/protected
---

# Browser Automation Stack

## Tool Selection

| Tool | Engine | Scope | Stealth |
|------|--------|-------|---------|
| **proofshot + agent-browser** | Chromium (CDP) | Local services (localhost) | ❌ |
| **camoufox** | Firefox (Juggler) | External/protected sites | ✅ |

### Decision Matrix
- **Local dev services** → proofshot
- **Login-protected external sites** → camoufox
- **Cloudflare/anti-bot bypass** → camoufox
- **Video recording + PR artifacts** → proofshot
- **Scraping with persistent sessions** → camoufox

No hybrid/bridge between Chromium + Firefox sessions needed.

## camoufox
- Install: `pip install -U camoufox[geoip] && camoufox fetch`
- Helper: `~/.hermes/skills/testing/camoufox-browser/scripts/camoufox_helper.py`
- Sessions: `~/.hermes/camoufox-sessions/<name>/`
- Skill: `camoufox-browser` (testing/)

## proofshot
- CLI: `/opt/homebrew/bin/proofshot`
- Browser: agent-browser (Chromium, `node_modules/.bin/agent-browser`)
- Commands: start, stop, diff, pr, exec, clean
- **Pitfall:** stale sessions → `agent-browser close` before start
- Skill: `run-proofshot-safe` (devops/)
