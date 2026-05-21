# X Thread: Cortex MCP Launch

**Status: SCHEDULED via Buffer — 2026-05-22 10:30-10:42 UTC**
**Account: @AliShaheen**

Images: `docs/images/cortex-benchmark-{1,2,3,4}.png`

---

## Tweet 1/7 — 10:30 UTC (Hook + Image 4: Before/After)

I replaced a 161MB compiled Go binary with 2MB of pure Python.

800x faster search. 650x smaller storage. And it does things the original never could.

Introducing Cortex MCP — unified code intelligence for AI agents.

Thread

[IMAGE: cortex-benchmark-4.png]

---

## Tweet 2/7 — 10:32 UTC (The Problem)

codebase-memory-mcp is solid — 14 tools, 64 langs.

But it only answers: "what is this code?"

Can't tell you WHY the code exists.
Can't tell you WHERE you left off.
Can't detect when code drifts from intent.

We needed all three.

---

## Tweet 3/7 — 10:34 UTC (Architecture + Image 3)

Cortex MCP — 3 layers:

STRUCTURE — WHAT the code is
AST parsing, symbol search, call graphs

INTENT — WHY the code exists
Design intents, drift detection

MEMORY — WHERE you left off
Session memory, checkpoints

15 tools. 1 server. pip install.

[IMAGE: cortex-benchmark-3.png]

---

## Tweet 4/7 — 10:36 UTC (Benchmarks + Image 1)

Benchmarked on real codebase (FastAPI + React):

Symbol search: 0.15ms vs 200ms (800x)
Code search: 0.3ms vs 150ms (300x)
Re-index: <10ms vs 200ms (20x)
Binary: 2MB vs 161MB (80x)
DB: 4KB vs 2.6MB (650x)

SQLite + FTS5 is absurdly fast for code intelligence.

[IMAGE: cortex-benchmark-1.png]

---

## Tweet 5/7 — 10:38 UTC (Killer Feature + Image 2)

The feature no other MCP server has: cortex_explain

One call returns:
- Structure: signature, location, call graph
- Intent: goal, owner, drift status
- Memory: last touched, related context, risk

Three layers. One answer.

[IMAGE: cortex-benchmark-2.png]

---

## Tweet 6/7 — 10:40 UTC (Technical Decisions)

Technical choices:

- sync sqlite3 + writer thread
- stat pre-filter before SHA-256
- FTS5 unicode61 (Porter mangles code)
- AST for Python, regex for TS/Go/Rust
- BM25 ranked search
- Recursive CTEs (no Cypher)

5 langs AI engineers use > 64 nobody needs.

---

## Tweet 7/7 — 10:42 UTC (CTA)

172 tests. All green.
Benchmarked against the tool it replaces.

Next: intent bootstrap from git history, SSE for Claude Desktop, tree-sitter.

Built with Claude Code + DeepSeek + Gemini + Kimi.
Multi-model dev is the future.
