---
name: workspace
description: Dynamic multi-repo and monorepo awareness for Claude Code. Analyze workspace topology, track API contracts, and maintain cross-repo context.
when-to-use: When working across multiple repos or in a monorepo with shared dependencies
user-invocable: true
effort: high
---

# Workspace Analysis Skill

> Dynamic multi-repo and monorepo awareness for Claude Code. Analyze workspace topology, track API contracts, and maintain cross-repo context.

## The Problem

When you have separate frontend/backend repos (or monorepo with multiple apps), Claude Code operates in isolation. It doesn't know:

- API contracts between modules/repos
- Shared types and interfaces
- Full system architecture
- Cross-repo dependencies
- What changed in other parts of the system

This leads to:
- Duplicate type definitions
- API contract mismatches
- Breaking changes not caught until runtime
- Claude reimplementing things that exist elsewhere

---

## Solution: Dynamic Workspace Analysis

Instead of static manifests that get stale, Claude dynamically analyzes the workspace and generates context artifacts that stay fresh through hooks.

```
┌─────────────────────────────────────────────────────────────────┐
│  WORKSPACE ANALYSIS SYSTEM                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  /analyze-workspace (Full Analysis - ~2 min)                     │
│  ├── Topology discovery (monorepo vs multi-repo)                │
│  ├── Dependency graph (who calls whom)                          │
│  ├── Contract extraction (OpenAPI, GraphQL, types)              │
│  └── Key file identification (what to load when)                │
│                                                                  │
│  /sync-contracts (Incremental - ~15 sec)                         │
│  ├── Check contract source files for changes                    │
│  ├── Update CONTRACTS.md with diffs                             │
│  └── Validate consistency                                       │
│                                                                  │
│  Hooks (Automatic)                                               │
│  ├── Session start: Staleness advisory (~5 sec)                 │
│  ├── Post-commit: Auto-sync if contracts changed (~15 sec)      │
│  └── Pre-push: Validation gate (~10 sec)                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Workspace Classification

### Detection Patterns

| Type | Indicators | File Access |
|------|------------|-------------|
| **Monorepo** | pnpm-workspace.yaml, nx.json, turbo.json, lerna.json | Direct (same tree) |
| **Multi-repo** | Sibling directories with separate .git | Via symlinks or paths |
| **Hybrid** | Monorepo + external repo dependencies | Mixed |
| **Single** | One app, no workspace config | N/A (use existing-repo) |

### Monorepo Detection

```bash
# Check for monorepo indicators
ls package.json pnpm-workspace.yaml lerna.json nx.json turbo.json 2>/dev/null
ls apps/ packages/ services/ libs/ modules/ 2>/dev/null
```

### Multi-Repo Detection

```bash
# Check sibling directories for related repos
ls -la ../*.git 2>/dev/null
cat ../*/.git/config 2>/dev/null | grep "url"

# Look for naming patterns
ls .. | grep -E "(frontend|backend|api|web|shared|common)"
```

### Polyglot Detection

```bash
# Find all package manifests
find . -maxdepth 4 -name "package.json" -o -name "pyproject.toml" \
  -o -name "go.mod" -o -name "Cargo.toml" -o -name "pom.xml" \
  -o -name "build.gradle" -o -name "Gemfile"
```

---

## Analysis Protocol

### Phase 1: Topology Discovery (~30 seconds)

Determine workspace structure:

```markdown
## Discovery Checklist

1. [ ] Identify workspace root
2. [ ] Classify workspace type (monorepo/multi-repo/hybrid/single)
3. [ ] List all modules/apps/packages
4. [ ] Detect tech stack per module
5. [ ] Identify entry points per module
```

**Module Detection Pattern:**

```
workspace-root/
├── apps/           → Application modules
│   ├── web/        → Frontend app
│   └── api/        → Backend app
├── packages/       → Shared packages
│   ├── ui/         → Component library
│   ├── types/      → Shared types
│   └── db/         → Database layer
├── services/       → Microservices
└── libs/           → Internal libraries
```

### Phase 2: Dependency Graph (~60 seconds)

For each module, map:

**1. Internal Dependencies**
```bash
# TypeScript/JavaScript
grep -r "from ['\"]@" --include="*.ts" --include="*.tsx" | head -50
grep -r "workspace:" package.json

# Python
grep -r "from \." --include="*.py" | head -50
```

**2. API Relationships**
```bash
# Find API calls
grep -rE "fetch|axios|httpx|requests\." --include="*.ts" --include="*.py" | \
  grep -E "/api|localhost|127\.0\.0\.1" | head -30
```

**3. Database Connections**
```bash
# Find DB access patterns
grep -rE "prisma|drizzle|sqlalchemy|sequelize|typeorm" --include="*.ts" --include="*.py"
```

### Phase 3: Contract Extraction (~45 seconds)

Identify and parse API contracts:

| Contract Type | Detection | Extraction |
|---------------|-----------|------------|
| **OpenAPI** | openapi.json, swagger.yaml, /docs endpoint | Parse paths, schemas |
| **GraphQL** | schema.graphql, *.gql, /graphql endpoint | Parse types, queries, mutations |
| **tRPC** | trpc router files, @trpc/* imports | Parse router definitions |
| **Protobuf** | *.proto files | Parse services, messages |
| **TypeScript** | Shared .d.ts, exported interfaces | Parse exported types |
| **Pydantic** | schemas/, models/ with BaseModel | Parse model definitions |
| **Zod** | schemas/ with z.object | Parse schema definitions |

**Contract Source Priority:**

1. Generated specs (openapi.json) - most accurate
2. Schema definitions (Pydantic, Zod) - source of truth
3. Type exports (TypeScript .d.ts) - consumer contracts
4. Inferred from code - last resort

### Phase 4: Key File Identification (~30 seconds)

Identify files Claude MUST know about for each context:

| Category | Detection Pattern | Token Priority |
|----------|-------------------|----------------|
| **Route definitions** | `**/routes/**`, `**/api/**`, `@app.get`, `@router` | HIGH |
| **Type definitions** | `**/types/**`, `*.d.ts`, `schemas/`, `models/` | HIGH |
| **Config** | `.env.example`, `config/`, `settings.py` | MEDIUM |
| **Entry points** | `main.ts`, `index.ts`, `app.py`, `server.py` | MEDIUM |
| **API clients** | `**/api/client*`, `**/lib/api*` | HIGH |
| **Database schema** | `schema/`, `migrations/`, `prisma/schema.prisma` | MEDIUM |
| **Tests** | `__tests__/`, `*_test.py`, `*.spec.ts` | LOW (on-demand) |

---

## Generated Artifacts

All artifacts go in `_project_specs/workspace/`:

```
_project_specs/workspace/
├── TOPOLOGY.md           # What modules exist, their roles
├── CONTRACTS.md          # API specs, shared types (summarized)
├── DEPENDENCY_GRAPH.md   # Who calls whom (visual + list)
├── KEY_FILES.md          # What to load for each context
├── CROSS_REPO_INDEX.md   # Capabilities across all modules
└── .contract-sources     # Files to monitor for changes
```

### TOPOLOGY.md Format

```markdown
# Workspace Topology

Generated: 2026-01-20T14:32:00Z
Analyzer: maggy/workspace-analysis
Workspace Type: Monorepo (Turborepo)

## Overview

```
┌─────────────────────────────────────────────────┐
│ apps/web (Next.js) ←→ apps/api (FastAPI)        │
│      ↓                      ↓                   │
│ packages/shared-types ← packages/db             │
└─────────────────────────────────────────────────┘
```

## Modules

### apps/web
- **Path**: /apps/web
- **Tech**: Next.js 14, TypeScript, TailwindCSS
- **Role**: Customer-facing dashboard
- **Consumes**: apps/api (REST), packages/shared-types
- **Entry**: src/app/layout.tsx
- **Key files**:
  - `src/lib/api/client.ts` - API client (187 lines)
  - `src/types/` - Frontend-specific types (12 files)
- **Token estimate**: ~15K (full), ~4K (summarized)

### apps/api
- **Path**: /apps/api
- **Tech**: FastAPI, Python 3.12, SQLAlchemy
- **Role**: REST API, business logic
- **Exposes**: OpenAPI at /docs (47 endpoints)
- **Consumes**: packages/db
- **Entry**: app/main.py
- **Key files**:
  - `app/routes/` - All endpoints (8 routers)
  - `app/schemas/` - Pydantic models (23 files)
  - `openapi.json` - Generated spec
- **Token estimate**: ~22K (full), ~6K (summarized)

### packages/shared-types
- **Path**: /packages/shared-types
- **Tech**: TypeScript
- **Role**: Shared type definitions
- **Consumed by**: apps/web, apps/api (codegen)
- **Key files**:
  - `src/index.ts` - All exports (340 lines)
- **Token estimate**: ~3K

### packages/db
- **Path**: /packages/db
- **Tech**: Drizzle ORM, TypeScript
- **Role**: Database schema, migrations
- **Consumed by**: apps/api
- **Key files**:
  - `schema/` - Table definitions (8 files)
  - `migrations/` - Migration history (23 files)
- **Token estimate**: ~8K (full), ~2K (schema only)
```

### CONTRACTS.md Format

```markdown
# API Contracts

Generated: 2026-01-20T14:32:00Z
Last sync: 2026-01-20T16:45:00Z
Sources: 3 files monitored

## REST API: apps/api → apps/web

### Endpoints Summary (47 total)

| Domain | Count | Key Endpoints |
|--------|-------|---------------|
| /api/auth | 5 | POST /login, POST /register, POST /refresh |
| /api/users | 6 | GET /me, PATCH /me, GET /:id |
| /api/campaigns | 8 | CRUD + POST /bulk, GET /analytics |
| /api/analytics | 12 | GET /dashboard, GET /timeseries, GET /funnel |
| /api/settings | 4 | GET /, PATCH /, GET /integrations |

### Key Types

```typescript
// Campaign domain (from apps/api/app/schemas/campaign.py)
interface Campaign {
  id: string;
  name: string;
  status: 'draft' | 'active' | 'paused' | 'completed';
  budget: number;
  target_audience: TargetAudience;
  created_at: string;
  updated_at: string;
}

interface CampaignCreate {
  name: string;
  budget: number;
  target_audience?: TargetAudience;
}

// Auth domain (from apps/api/app/schemas/auth.py)
interface User {
  id: string;
  email: string;
  name: string;
  role: 'user' | 'admin';
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}
```

### Contract Validation Status

| Check | Status | Details |
|-------|--------|---------|
| OpenAPI matches routes | ✅ | 47/47 endpoints documented |
| Types match schemas | ✅ | All Pydantic models exported |
| Frontend types current | ⚠️ | 2 types need regeneration |

## Shared Types: packages/shared-types

### Exported Types (34 total)

| Category | Types | Used By |
|----------|-------|---------|
| Domain models | Campaign, User, Analytics | web, api |
| API responses | ApiResponse<T>, PaginatedResponse<T> | web |
| Utilities | DateRange, FilterParams | web, api |

## Database Schema: packages/db

### Tables (12 total)

| Table | Key Columns | Relations |
|-------|-------------|-----------|
| users | id, email, name, role | campaigns, sessions |
| campaigns | id, user_id, name, status | analytics, targets |
| analytics | id, campaign_id, date, metrics | campaigns |
```

### DEPENDENCY_GRAPH.md Format

```markdown
# Dependency Graph

Generated: 2026-01-20T14:32:00Z

## Visual Overview

```
                    ┌─────────────────┐
                    │  packages/db    │
                    │  (Drizzle ORM)  │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────┐   ┌─────────────────┐
│    apps/web     │◄──│    apps/api     │
│   (Next.js)     │   │   (FastAPI)     │
└────────┬────────┘   └────────┬────────┘
         │                     │
         ▼                     ▼
┌─────────────────────────────────────────┐
│        packages/shared-types            │
│           (TypeScript)                  │
└─────────────────────────────────────────┘
```

## Dependency Matrix

| Module | Depends On | Depended By |
|--------|------------|-------------|
| apps/web | shared-types, apps/api (runtime) | - |
| apps/api | shared-types (codegen), db | apps/web |
| packages/shared-types | - | apps/web, apps/api |
| packages/db | - | apps/api |

## Import Analysis

### apps/web imports:
```
@repo/shared-types: 23 files
apps/api (via fetch): 15 files
```

### apps/api imports:
```
packages/db: 12 files
packages/shared-types (codegen): 8 files
```

## API Call Graph

```
apps/web                          apps/api
─────────                         ────────
src/lib/api/client.ts ──────────► app/routes/auth.py
  └── login()          POST /api/auth/login
  └── register()       POST /api/auth/register

src/app/campaigns/page.tsx ─────► app/routes/campaigns.py
  └── getCampaigns()   GET /api/campaigns
  └── createCampaign() POST /api/campaigns
```
```

### KEY_FILES.md Format

```markdown
# Key Files by Context

## Context: Frontend API Integration
**When**: Modifying API calls, response handling, or API types in frontend

Load these files (~8K tokens):
```
apps/web/src/lib/api/client.ts       # API client implementation
apps/web/src/types/api.d.ts          # Frontend API types
apps/api/openapi.json                # Full API spec (or summary)
packages/shared-types/src/index.ts   # Shared type definitions
```

## Context: Backend Endpoint Development
**When**: Adding/modifying API endpoints

Load these files (~12K tokens):
```
apps/api/app/routes/                 # Existing route patterns
apps/api/app/schemas/                # Pydantic models (relevant domain)
apps/api/app/dependencies/           # Auth, DB dependencies
packages/db/schema/                  # Relevant table definitions
```

## Context: Database Changes
**When**: Schema modifications, migrations, queries

Load these files (~6K tokens):
```
packages/db/schema/                  # All table definitions
packages/db/migrations/              # Last 5 migrations
apps/api/app/models/                 # ORM model usage
```

## Context: Shared Types
**When**: Modifying interfaces used across modules

Load these files (~4K tokens):
```
packages/shared-types/src/           # Type source files
apps/web/src/types/api.d.ts          # Consumer (frontend)
apps/api/app/schemas/                # Source (backend)
```

## Context: Authentication
**When**: Auth flow, sessions, tokens

Load these files (~5K tokens):
```
apps/api/app/routes/auth.py          # Auth endpoints
apps/api/app/dependencies/auth.py    # Auth middleware
apps/web/src/lib/auth/               # Frontend auth handling
packages/shared-types/src/auth.ts    # Auth types
```

## Load-on-Demand Triggers

| Claude detects... | Load additionally |
|-------------------|-------------------|
| "check the API contract" | Full OpenAPI spec |
| Import from another module | That module's exports |
| Database query pattern | Full schema definitions |
| Test failure in other module | That module's test files |
| "breaking change" | Both sides of the contract |
```

### CROSS_REPO_INDEX.md Format

```markdown
# Cross-Repository Capability Index

Generated: 2026-01-20T14:32:00Z

## Capabilities by Domain

### Authentication
| Capability | Location | Module | Type |
|------------|----------|--------|------|
| Login user | POST /api/auth/login | apps/api | endpoint |
| Register user | POST /api/auth/register | apps/api | endpoint |
| Refresh token | POST /api/auth/refresh | apps/api | endpoint |
| Auth context | src/contexts/AuthContext.tsx | apps/web | component |
| Auth hook | src/hooks/useAuth.ts | apps/web | hook |
| User type | src/auth.ts | shared-types | type |
| Session type | src/auth.ts | shared-types | type |

### Campaigns
| Capability | Location | Module | Type |
|------------|----------|--------|------|
| List campaigns | GET /api/campaigns | apps/api | endpoint |
| Create campaign | POST /api/campaigns | apps/api | endpoint |
| Campaign CRUD | app/routes/campaigns.py | apps/api | router |
| Campaign form | src/components/CampaignForm.tsx | apps/web | component |
| Campaign type | src/campaign.ts | shared-types | type |
| campaigns table | schema/campaigns.ts | packages/db | table |

### Analytics
| Capability | Location | Module | Type |
|------------|----------|--------|------|
| Dashboard data | GET /api/analytics/dashboard | apps/api | endpoint |
| Timeseries | GET /api/analytics/timeseries | apps/api | endpoint |
| Analytics hook | src/hooks/useAnalytics.ts | apps/web | hook |
| Chart components | src/components/charts/ | apps/web | components |

## Search Index

Before implementing new functionality, search this index:

```
Q: "How do I get the current user?"
A: Use useAuth() hook from apps/web/src/hooks/useAuth.ts
   Or GET /api/users/me endpoint from apps/api

Q: "Where are campaign types defined?"
A: Source of truth: packages/shared-types/src/campaign.ts
   Backend schema: apps/api/app/schemas/campaign.py
   Frontend types: apps/web/src/types/api.d.ts (generated)

Q: "How do I add a new API endpoint?"
A: Pattern in apps/api/app/routes/campaigns.py
   Register in apps/api/app/routes/__init__.py
   Add types to packages/shared-types
   Regenerate frontend types
```
```

---

## Token Budget Management

### Context Limits

```
┌─────────────────────────────────────────────────────────────────┐
│  TOKEN BUDGET ALLOCATION                                         │
├─────────────────────────────────────────────────────────────────┤
│  Total context: ~200K tokens                                     │
│  Reserve for output: ~50K tokens                                 │
│  Working budget: ~150K tokens                                    │
├─────────────────────────────────────────────────────────────────┤
│  P0 (Must have):     50K │ Current module (full)                │
│  P1 (Should have):   40K │ Directly related modules (summary)   │
│  P2 (Nice to have):  30K │ Contracts + shared types             │
│  P3 (If room):       20K │ Decisions, todos, history            │
│  Buffer:             10K │ Dynamic loading during session       │
└─────────────────────────────────────────────────────────────────┘
```

### Automatic Summarization

When loading cross-module context, summarize:

| Content Type | Full Load Threshold | Summarization Strategy |
|--------------|---------------------|------------------------|
| OpenAPI spec | < 50 endpoints | Endpoints + key types only |
| Type files | < 30 types | Exported types only |
| Route files | < 200 lines | Signatures + docstrings |
| Config files | < 50 lines | Keys only (no values/secrets) |
| Test files | Never full | Only on explicit request |

### Context Loading Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│  CONTEXT LOADING HIERARCHY                                       │
├─────────────────────────────────────────────────────────────────┤
│  Level 1: Always loaded (~5K tokens)                             │
│  ├── TOPOLOGY.md (workspace structure)                          │
│  ├── CONTRACTS.md (API summary)                                 │
│  └── CROSS_REPO_INDEX.md (capability search)                    │
│                                                                  │
│  Level 2: Loaded based on current file (~15K tokens)            │
│  ├── KEY_FILES.md recommendations for current context           │
│  ├── Related module summaries                                   │
│  └── Relevant type definitions                                  │
│                                                                  │
│  Level 3: On-demand expansion (variable)                        │
│  ├── Full OpenAPI spec (when "check API contract")              │
│  ├── Full type files (when modifying interfaces)                │
│  └── Other module's full files (when cross-repo change)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-Repo File Access

For multi-repo workspaces (separate .git directories):

### Option 1: Sibling Directory Convention (Recommended)

```
~/code/
├── myapp-frontend/     # git repo
├── myapp-backend/      # git repo
├── myapp-shared/       # git repo
└── .workspace/         # workspace config (optional)
    └── myapp.yaml
```

Claude accesses via relative paths: `../myapp-backend/`

### Option 2: Workspace Symlinks

```bash
# In frontend repo
mkdir -p .workspace/repos
ln -s ../../myapp-backend .workspace/repos/backend
ln -s ../../myapp-shared .workspace/repos/shared
```

### Option 3: Git Submodules

```bash
# Add related repos as submodules (read-only)
git submodule add --depth 1 ../myapp-shared .workspace/shared
```

### File Access Rules

```markdown
## Multi-Repo Access Protocol

WHEN accessing files from another repo:
1. Use relative paths from workspace root
2. Read-only access (never modify other repos)
3. Cache contract files locally in _project_specs/workspace/cache/
4. Log cross-repo reads in decisions.md

BEFORE making cross-repo changes:
1. Document the change in BOTH repos' decisions.md
2. Create linked todos in BOTH repos
3. Implement in dependency order (shared → backend → frontend)
```

---

## Cross-Repo Change Detection

When Claude detects changes that affect other modules:

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  CROSS-REPO CHANGE DETECTED                                  │
├─────────────────────────────────────────────────────────────────┤
│  This change affects: apps/api                                   │
│  Specifically: Endpoint POST /api/campaigns expects new field    │
│                                                                  │
│  Impact Analysis:                                                │
│  ├── apps/web/src/lib/api/client.ts - needs update              │
│  ├── packages/shared-types/src/campaign.ts - needs new field    │
│  └── apps/api/app/schemas/campaign.py - source of change        │
│                                                                  │
│  Recommended Order:                                              │
│  1. Update packages/shared-types first (source of truth)         │
│  2. Update apps/api schema                                       │
│  3. Regenerate frontend types                                    │
│  4. Update apps/web API client                                   │
│  5. Run /sync-contracts                                          │
│                                                                  │
│  [Proceed with guidance] [Load full context] [Cancel]            │
└─────────────────────────────────────────────────────────────────┘
```

### Change Impact Patterns

| Change Type | Impacts | Action |
|-------------|---------|--------|
| New API endpoint | Frontend client, types | Add to both, sync contracts |
| Modified response | Frontend types, tests | Regenerate types, update tests |
| New required field | All consumers | Breaking change protocol |
| Renamed field | All consumers | Migration + deprecation |
| New shared type | Consumers on next use | Export from shared-types |
| Schema migration | API models, queries | Run migration, verify queries |

---

## Contract Freshness System

### Staleness Detection

```bash
# .contract-sources file (auto-generated)
# Files that define contracts - monitored for changes

# OpenAPI specs
apps/api/openapi.json
apps/api/docs/openapi.yaml

# Type definitions
packages/shared-types/src/index.ts
packages/shared-types/src/api.ts

# Pydantic schemas
apps/api/app/schemas/*.py

# Database schema
packages/db/schema/*.ts
```

### Freshness Tiers

| Tier | Trigger | Action | Time | Blocking |
|------|---------|--------|------|----------|
| 1 | Session start | Staleness check | ~5s | No |
| 2 | Post-commit | Auto-sync if contracts changed | ~15s | No |
| 3 | Pre-push | Validation gate | ~10s | Yes (bypassable) |
| 4 | PR opened | CI validation | ~30s | Yes |
| 5 | Weekly cron | Full re-analysis | ~2min | No |

### Freshness Indicators

```markdown
## Contract Status (shown in CONTRACTS.md header)

Last full analysis: 2026-01-18T10:00:00Z
Last sync: 2026-01-20T14:32:00Z
Staleness: 🟢 Fresh (synced 2 hours ago)

## Confidence Levels

🟢 Fresh     - Synced within 24 hours, no source changes
🟡 Stale     - Sources changed since last sync
🔴 Outdated  - Over 7 days since last analysis
⚠️  Drift    - Validation found inconsistencies
```

---

## Integration with Existing Skills

### With existing-repo.md

`workspace.md` calls `existing-repo.md` analysis for each module:

```markdown
## Module Analysis Delegation

For each module in workspace:
1. Run existing-repo analysis on that module
2. Extract: tech stack, conventions, guardrails status
3. Aggregate into TOPOLOGY.md
4. Don't duplicate - reference existing-repo output
```

### With session-management.md

```markdown
## Session State Integration

Workspace context files are part of session state:
- TOPOLOGY.md → structural context (rarely changes)
- CONTRACTS.md → API context (check freshness each session)
- KEY_FILES.md → loading guidance (static reference)

On session start:
1. Load _project_specs/workspace/*.md into context
2. Check contract freshness
3. Advise if sync needed
```

### With code-review.md

```markdown
## Cross-Repo Review Checks

When reviewing code that touches contracts:

1. Check if change affects other modules
2. Verify contract consistency
3. Flag if CONTRACTS.md needs update
4. Warn about breaking changes

Add to review output:
### 🔗 Cross-Repo Impact
- [ ] This change affects: apps/web (API client)
- [ ] Contract update needed: Yes
- [ ] Breaking change: No
```

---

## Commands

### /analyze-workspace

Full workspace analysis - run on first setup or major changes.

See `commands/analyze-workspace.md` for full specification.

### /sync-contracts

Lightweight incremental contract update - run frequently.

See `commands/sync-contracts.md` for full specification.

### /workspace-status

Quick status check:

```
📊 Workspace Status: myapp

Type: Monorepo (Turborepo)
Modules: 4 (2 apps, 2 packages)
Contracts: 🟢 Fresh (synced 2h ago)
Token estimate: 45K / 150K budget

Quick actions:
  /sync-contracts     - Update contracts
  /analyze-workspace  - Full refresh
```

---

## CI/CD Integration

### GitHub Actions: Contract Validation

```yaml
# .github/workflows/contracts.yml
name: Contract Validation

on:
  pull_request:
    paths:
      - 'apps/api/**'
      - 'packages/shared-types/**'
      - 'packages/db/schema/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check contract freshness
        run: |
          CHANGED=$(git diff --name-only origin/main HEAD | \
            grep -E "openapi|schema|types" || true)

          if [ -n "$CHANGED" ]; then
            echo "Contract sources changed:"
            echo "$CHANGED"

            if ! git diff --name-only origin/main HEAD | grep -q "CONTRACTS.md"; then
              echo "::error::Contract sources changed but CONTRACTS.md not updated"
              echo "Run /sync-contracts before merging"
              exit 1
            fi
          fi

      - name: Validate consistency
        run: |
          if [ -f "apps/api/openapi.json" ]; then
            ENDPOINTS=$(jq -r '.paths | keys | length' apps/api/openapi.json)
            DOCUMENTED=$(grep -c "^| /" _project_specs/workspace/CONTRACTS.md || echo 0)

            if [ "$ENDPOINTS" != "$DOCUMENTED" ]; then
              echo "::warning::Endpoint count mismatch"
            fi
          fi
```

### Pre-commit Hook

```bash
#!/bin/bash
# hooks/pre-commit-contracts

WORKSPACE_DIR="_project_specs/workspace"
[ ! -f "$WORKSPACE_DIR/.contract-sources" ] && exit 0

# Check if staged files include contract sources
STAGED=$(git diff --cached --name-only)
CONTRACT_SOURCES=$(cat "$WORKSPACE_DIR/.contract-sources")

for source in $CONTRACT_SOURCES; do
  if echo "$STAGED" | grep -q "$source"; then
    echo "📝 Contract source staged: $source"
    echo "Remember to run /sync-contracts before pushing"
  fi
done
```

---

## Troubleshooting

### "Workspace not detected"

```bash
# Check for workspace indicators
ls -la package.json pnpm-workspace.yaml turbo.json nx.json 2>/dev/null

# If multi-repo, check sibling directories
ls -la ../

# Manual classification
/analyze-workspace --type monorepo
/analyze-workspace --type multi-repo --repos "../backend,../shared"
```

### "Contract sync failed"

```bash
# Check contract sources exist
cat _project_specs/workspace/.contract-sources

# Verify file access
for f in $(cat .contract-sources); do
  ls -la "$f" 2>/dev/null || echo "Missing: $f"
done

# Force full refresh
/analyze-workspace --force
```

### "Token budget exceeded"

```bash
# Check current estimates
/workspace-status

# Reduce context loading
# Edit KEY_FILES.md to prioritize
# Or work on one module at a time
```

### "Cross-repo access denied"

```bash
# Check paths are correct
ls ../backend/  # or wherever related repo is

# Set up symlinks if needed
mkdir -p .workspace/repos
ln -s ../../backend .workspace/repos/backend

# Or configure in workspace
/analyze-workspace --repo-path backend=../myapp-backend
```
