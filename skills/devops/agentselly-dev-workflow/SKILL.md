---
name: agentselly-dev-workflow
description: Local dev workflow — single app mode via Doppler, full stack via Docker
---

# AgentSelly Dev Workflow

## Two Modes

### Single App — `pnpm dev:start <app>`
- Doppler `dev_local` config (Cloud DBs, Secrets)
- No Docker, no Portless
- Foreground, Ctrl+C kills
- Auto-strips `portless run` + `../../tools/doppler-dev.sh` wrapper
```bash
pnpm dev:start consumer-calculator
pnpm dev:start mq-handler -- --debug  # passthrough args
```

### Full Stack — `pnpm dev`
- Docker infra: MongoDB, Redis, RabbitMQ, PostgreSQL, FTP, N8N
- RabbitMQ topology (11 queues, exchanges, bindings, dead-letters)
- Portless URLs, `.env.local` overrides (localhost DBs)
- All apps via turbo + Agency

## dev-app.mjs Internals
1. Read `apps/<app>/doppler.yaml` → project name
2. Read `apps/<app>/package.json` → dev script
3. Strip `portless run ../../tools/doppler-dev.sh` prefix (handles chained patterns)
4. Run: `doppler run --project <name> --config dev_local -- <raw command>`

### Pattern Stripping
| Pattern | Stripped Result |
|---------|-----------------|
| `portless run ../../tools/doppler-dev.sh nest start --watch` | `nest start --watch` |
| `portless run ../../tools/doppler-dev.sh sh -c '...'` | `sh -c '...'` |
| Chained: `portless run export X=1 && ../../tools/doppler-dev.sh ...` | `export X=1 && ...` |
| Shell script wrapper | `./script.sh` |

## Doppler Project Exceptions
- `consumer-pitchdeck` → project `consumer-booklet`
- `immodossier-client`, `immodossier-shared` → no Doppler project
- `browser-use`, `fleet`, `agents` → no Doppler config
