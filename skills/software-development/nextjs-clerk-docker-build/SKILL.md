---
name: nextjs-clerk-docker-build
description: Fix Next.js + Clerk build failure in Docker — force-dynamic in root layout
---

# Next.js + Clerk Docker Build

## Problem
Static prerendering fails when `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` unavailable at build time:
```
Error: @clerk/clerk-react: Missing publishableKey
Error occurred prerendering page "/_not-found"
```

## Fix
Add to **root layout.tsx**:
```tsx
export const dynamic = 'force-dynamic';
```
- Skips ALL static prerendering → all pages server-rendered on demand

## When to Apply
- Docker builds without Clerk production keys
- CI/CD where Clerk keys aren't injected at build time
- Any env where `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is unset during `next build`

## Caveats
- ALL pages become dynamic (no static optimization)
- Acceptable for fully auth-gated apps
- Per-page `export const dynamic = 'force-static'` overrides possible where needed
