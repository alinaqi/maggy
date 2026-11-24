# Phase 7: Isolated Vercel Deploy Containers

**Status:** superseded. The in-memory stubs `deploy.py` and `api/routes_deploy.py` were deleted in the personal-harness Phase 6 cleanup (see `docs/rfc-personal-harness.md`); the deliverables below are historical.
**Priority:** P2 — enables parallel deploys without auth conflicts
**Effort:** Medium
**Dependencies:** Docker (for container isolation)

---

## Scope

Build isolated deployment containers that allow multiple projects to deploy to Vercel simultaneously without auth conflicts. Each container has its own Chrome profile, Vercel session, and isolated filesystem. This solves the problem of Vercel CLI sessions conflicting when multiple agents try to deploy at the same time.

## What Gets Built

1. **Vercel session container** (`templates/Dockerfile.vercel-session`)
   - Base: Node.js + Chrome (Playwright)
   - Isolated Chrome profile per container (Docker volume)
   - Vercel CLI pre-installed and authenticated per-project
   - Playwright for any browser-based auth flows

2. **Deploy orchestrator** (`maggy/maggy/deploy.py`)
   - Queue deploy requests per project
   - Spawn container per deploy (reuse if project container exists)
   - Capture deploy logs and preview URLs
   - Report results to Maggy dashboard

3. **Multi-project deploy**
   - Up to N projects deploying in parallel (default N=4)
   - Each in its own container with its own Vercel token
   - Preview URLs appear in dashboard as they complete
   - Deploy status: queued → building → deployed → live

4. **Auth management**
   - Per-project Vercel tokens stored in `~/.maggy/deploy-tokens.yaml`
   - Token rotation when auth expires
   - Never shared between containers

## Deliverables

- [ ] `templates/Dockerfile.vercel-session` — Deploy container image
- [ ] `maggy/maggy/deploy.py` — Deploy orchestrator
- [ ] `maggy/maggy/api/routes_deploy.py` — Deploy status endpoints
- [ ] `tests/test_deploy.py` — Deploy orchestration tests (mock Vercel)
- [ ] Dashboard deploy status panel

## Success Criteria

- [ ] 4 projects can deploy in parallel without auth conflicts
- [ ] Preview URLs appear in dashboard within 30s of deploy start
- [ ] Container startup < 10s (pre-built image)
- [ ] Auth tokens are never shared between containers
- [ ] Failed deploys surface clear error messages
- [ ] All tests pass, coverage >= 80%

## Risks

- Chrome/Playwright adds significant image size (~1GB) — consider lighter alternatives
- Vercel rate limits may throttle parallel deploys — add backoff logic
- Token management across projects adds operational complexity
