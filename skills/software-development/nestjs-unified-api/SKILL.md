---
name: nestjs-unified-api
description: NestJS monorepo patterns — logger migration, lockfile drift, app structure, VAB export
---

# NestJS Unified API

## @agentselly/logger Migration

| NestJS Logger | @agentselly/logger |
|---|---|
| `.log()` | **`.info()`** (no `.log()` method!) |
| `.error()/.warn()/.debug()` | Same |
| `new Logger(name)` | `createLogger(name)` |

### Before/After
```typescript
// Before
import { Injectable, Logger } from '@nestjs/common';
private readonly logger = new Logger(MyService.name);
this.logger.log('message');

// After
import { Injectable } from '@nestjs/common';
import { createLogger } from '@agentselly/logger';
private readonly logger = createLogger(MyService.name);
this.logger.info('message');
```

- Bridge files `app/util/NestLoggerService.ts` implement NestJS `LoggerService` interface
  - Keep `import type { LoggerService } from '@nestjs/common'` — correct, must stay

## Lockfile Drift on Feature Branches

**Symptom:** `ERR_PNPM_OUTDATED_LOCKFILE` in CI

**Fix:**
```bash
git checkout main && git pull
git checkout <feature-branch>
git rebase main
# If lockfile conflicts: git checkout main -- pnpm-lock.yaml
git diff main -- pnpm-lock.yaml | wc -l  # Must be 0
git push --force-with-lease
```

## App Structure
- `apps/<name>/app/` — nest-cli.json sourceRoot = "app"
- `modules/<name>/src/` — shared modules
- `packages/<name>/src/` — shared packages

## ReportsService — VAB Export
- **File:** `app/services/ReportsService.ts`
- **Controller:** `app/controllers/ReportsController.ts` → `GET /v1/reports/export`
- `deal_id` = HubSpot internal ID, always included (not a property, never stripped)
- `DEFAULT_DEAL_PROPERTIES`: custom fields like `internalagent`, `sales_manager`, `lead_bringer`, VAB timestamps
- `DEFAULT_CONTACT_PROPERTIES`: includes `real_estate_object_city`
- `closed_lost_reason` — NOT yet in DEFAULT_DEAL_PROPERTIES
- **VAB Filter:** Lead-Source Type VAB, 2026 leads or active, 2026 completions/cancellations
