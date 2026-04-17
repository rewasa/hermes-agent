---
name: hubspot-crm-cards
description: HubSpot CRM card patterns — calendar controller, VisitManager card, shared UI package
---

# HubSpot CRM Cards

## Shared UI Package (DEV-1647)
- React 18, Tailwind CSS
- `PropertyCard` component for CRM card reuse

## Calendar Controller (DEV-1712)
- Endpoints: `/v1/calendar/events`, `/v1/calendar/availability`, `/v1/calendar/book`
- CalendarService: MongoDB (primary) + HubSpot Meetings (fallback)
- Writes to MongoDB + HubSpot Meeting sync
- DTOs: `app/dtos/CalendarEventDto.ts` (6 DTOs)

## VisitManager Card
- Location: `apps/hubspot-ui-extensions/src/app/dist/VisitManagerCard.js`
- Runs in HubSpot iframe sandbox — **no source in repo**, only compiled dist
- **Cannot test locally with proofshot** — needs HubSpot login + browser session

## Key Patterns
- `hubspotRequest()` is **private** in HubSpotService — add public methods or use own fetch with `HUBSPOT_TOKEN`
- `CalendarEventType` and `CalendarEventSyncStatus` are **type aliases** (not enums) — use `@IsIn([...])` not `@IsEnum()`
