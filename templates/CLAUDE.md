# CLAUDE.md

## Skills
@.claude/skills/base/SKILL.md
@.claude/skills/iterative-development/SKILL.md
@.claude/skills/security/SKILL.md

## Project Context
- Language: [e.g., TypeScript]
- Framework: [e.g., Next.js 14 (App Router)]
- Database: [e.g., Supabase/PostgreSQL]
- ORM: [e.g., Drizzle]
- Testing: [e.g., Vitest]
- Auth: [e.g., Supabase Auth]

## Commands
[npm test]                     # run tests
[npm run test:coverage]        # tests with coverage
[npm run lint]                 # lint
[npm run typecheck]            # type check
[npm run dev]                  # local dev server

## Project Structure
[Fill in after project setup, e.g.:]
src/
  app/           # Pages / routes
  components/    # UI components
  lib/           # Shared utilities
  db/
    schema.ts    # Database schema — read before any DB code
    migrations/  # Database migrations
  api/           # API route handlers

## Key Decisions
[Document settled architectural choices so Claude doesn't re-litigate them, e.g.:]
- [ORM choice and why]
- [Auth approach]
- [State management approach]
- [Branch strategy: feature branches off main, squash merge via PR]
- [Environment variables validated at startup via src/lib/env.ts]

## Conventions
[Document patterns Claude should follow, e.g.:]
- Colocated tests: Component.test.tsx next to Component.tsx
- API routes return { data, error } shape
- Database queries go through src/db/queries/ — never raw SQL in routes
- Use existing utilities before creating new ones — check src/lib/ first

## Don't
- Don't modify .env files
- Don't add packages without checking if existing deps cover the need
- Don't put secrets in client-exposed env vars (NEXT_PUBLIC_*, VITE_*)
- Don't skip the test phase
