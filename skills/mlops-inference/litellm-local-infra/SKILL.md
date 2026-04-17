---
name: litellm-local-infra
description: LiteLLM proxy + OMLX local LLM infrastructure — config, ports, model routing, compression
---

# LiteLLM Local Infrastructure

## Config Paths
| What | Path |
|------|------|
| **Active config** (mounted in container) | `~/GIT/AgentSelly/monorepo/litellm-standalone/config/config.yaml` |
| Legacy config (NOT active!) | `~/GIT/AgentSelly/monorepo/litellm_config.yaml` |
| OMLX models dir | `~/.omlx/models/` |
| OMLX settings | `~/.omlx/settings.json` |
| Compression middleware | `litellm-standalone/config/custom_callback/compression_middleware.py` |

## Ports
- OMLX: `localhost:8000`
- LiteLLM Proxy: `localhost:4000`
- Docker: `4000/tcp → 0.0.0.0:4000`

## API Keys
| Key | Env Var |
|-----|---------|
| Z.AI / GLM-5-Turbo | `GLM_API_KEY` (in `~/.hermes/.env`) |
| Z.AI Base URL | `https://api.z.ai/api/coding/paas/v4` |
| OMLX | `sk-age...ocal` |
| LiteLLM Master | `sk-age...ocal` |

## Local Models (M5 Max 48GB)
| Model | Dir | Size | Use |
|-------|-----|------|-----|
| **Gemma-4-31B-it-4bit** | `Gemma-4-31B-it-4bit/` | 18GB | **tier-simple + tier-medium** (vision, 256K ctx) |
| Qwen3.5-27B-Text-mxfp4 | `Qwen3.5-27B-Text-mxfp4/` | 14GB | Fallback (`omlx` alias), dense text |
| Qwen3-Coder-30B-A3B | `Qwen3-Coder-30B-A3B-Instruct-4bit/` | 16.8GB | Legacy (`omlx-coder-30b`) |
| Qwen2.5-Coder-7B | `Qwen2.5-Coder-7B-Instruct-4bit/` | 4.2GB | Legacy |
| gpt-oss-20b | `gpt-oss-20b-MXFP4-Q4/` | 10.9GB | Legacy |

- MLX format required (config.json + *.safetensors) — GGUF won't work with OMLX
- Directory name MUST match LiteLLM model ID (OMLX auto-detects by dir name)

## Model Routing
- **tier-simple** → Gemma-4-31B (local, vision, 256K ctx)
- **tier-medium** → Gemma-4-31B (local, max_tokens=65536)
- **tier-complex** → Copilot Sonnet 4.6 / Opus 4.6 Fast / Vertex Gemini 2.5 Pro
- **tier-reasoning** → Copilot Opus 4.6 / GPT 5.4 / Vertex Gemini 2.5 Pro
- **smart-router**: ComplexityRouter auto-selects tier by prompt complexity
- **Chat model** (Hermes Discord): Direct ZAI, NOT via LiteLLM Proxy
- **Via Proxy**: Compression (summary_model=litellm/omlx), cron jobs, subagents
- **Databricks REMOVED** (Apr 2026)

## Fallback DAG Rules (MANDATORY)
1. NO self-reference (no `tier-complex → tier-complex`)
2. NO bidirectional (no `opus-46 ↔ opus-46-fast`)
3. Tiers only UPWARD (simple→medium→complex→reasoning)
4. Copilot only NEWER (46→never 45)
5. Leaf nodes = dead-ends (vertex, zai-glm have no fallbacks)
6. Always run cycle check after changes → skill: `litellm-fallback-cycle-check`

## Compression Middleware
- **Class:** `PromptCompressionMiddleware` (CustomLogger)
- **Hook:** `async_pre_call_hook` — compresses old conversation turns
- **Threshold:** 40000 chars (>20 messages)
- **Summarizer:** local Qwen3-Coder-30B via OMLX (`host.docker.internal:8000`)
- Cloud-bound models: aggressive compression (512 vs 1024 max_tokens)
- Local models (omlx, tier-simple): skipped — no cloud tokens to save
- **Register via:** `litellm_custom.compression_middleware.proxy_handler_instance`
  - Must mount in `/app/litellm_custom/` (bug: callbacks with `.` in name lose config_file_path)

## Containers
- `litellm-proxy-standalone` — Proxy
- `litellm-postgres-standalone` — DB (Spend Logs, Error Logs, Model Table)
- `litellm-redis-standalone` — Semantic Cache

## Cache
- Redis Semantic Cache, similarity: 0.85, TTL: 7200s
- Embedding: text-embedding-004 (Vertex)

## DB Access
```bash
docker exec litellm-postgres-standalone psql -U litellm -d litellm
SELECT * FROM "LiteLLM_SpendLogs";
SELECT * FROM "LiteLLM_ErrorLogs";
```

## Pitfalls
- `litellm_config.yaml` is a COPY — NOT used by container!
- `docker restart` sometimes insufficient — need `stop + start`
- Custom callbacks SILENTLY fail on bad path — check logs for `ImportError`
- Copilot models share quota — one 402 fails ALL copilot models
- Container crash-loop on bad callback config — revert config, fix, re-enable
