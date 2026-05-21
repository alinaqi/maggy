# X Thread: Cortex MCP Launch

Images saved at `/tmp/cortex-benchmark-{1,2,3,4}.png`

---

## Tweet 1/7 (Hook + Image 4: Before/After)

I replaced a 161MB compiled Go binary with 2MB of pure Python.

It's 800x faster at search. 650x smaller storage. And it does things the original never could.

Introducing Cortex MCP — unified code intelligence for AI agents.

Thread on what we built and why.

[IMAGE: cortex-benchmark-4.png — Before/After comparison]

---

## Tweet 2/7 (The Problem)

codebase-memory-mcp is great — 14 tools, 64 languages, solid graph.

But it only answers ONE question: "what is this code?"

It can't tell you WHY the code exists.
It can't tell you WHERE you left off yesterday.
It can't detect when code drifts from its original intent.

We needed all three.

---

## Tweet 3/7 (Architecture + Image 3: Three Layers)

So we built Cortex MCP with 3 layers:

STRUCTURE — WHAT the code is
AST parsing, symbol search, call graphs, route detection

INTENT — WHY the code exists
Design intents, drift detection, contracts

MEMORY — WHERE you left off
Session memory, checkpoints, fatigue tracking

15 tools. 1 server. pip install.

[IMAGE: cortex-benchmark-3.png — Three layers diagram]

---

## Tweet 4/7 (Benchmark Numbers + Image 1: Comparison Chart)

Benchmarked on a real codebase (40 files, FastAPI + React):

Symbol search: 0.15ms vs 50-200ms (800x faster)
Code search: 0.3ms vs 50-150ms (300x faster)
Re-index: <10ms vs 200ms (20x faster)
Binary: 2MB vs 161MB (80x smaller)
DB size: 4KB vs 2.6MB (650x smaller)

SQLite + FTS5 is absurdly fast for code intelligence.

[IMAGE: cortex-benchmark-1.png — Benchmark comparison]

---

## Tweet 5/7 (The Killer Feature + Image 2: cortex_explain)

The feature no other MCP server has:

cortex_explain("validateToken")

One call returns:
- Structure: signature, file location, call graph
- Intent: which goal it fulfills, who owns it, drift status
- Memory: when you last touched it, related context, risk level

Three layers. One answer. Zero extra tool calls.

[IMAGE: cortex-benchmark-2.png — cortex_explain output]

---

## Tweet 6/7 (Technical Decisions)

Key technical choices:

- sync sqlite3 + dedicated writer thread (not aiosqlite)
- stat pre-filter (mtime+size) before SHA-256 hashing
- FTS5 with unicode61 tokenizer (Porter mangles code identifiers)
- AST for Python, regex for TS/JS/Go/Rust
- BM25 ranked search (exact > prefix > contains)
- Recursive CTEs for graph traversal (no Cypher DSL)

5 languages that AI engineers actually use > 64 that nobody needs.

---

## Tweet 7/7 (CTA)

172 tests. All green.
Benchmarked against the tool it replaces.
Full comparison doc in the repo.

Next: intent bootstrapping from git history, SSE transport for Claude Desktop, and tree-sitter for deeper AST.

Built with Claude Code + DeepSeek Pro + Gemini + Kimi.
Multi-model dev is the future.

---

## Posting Order

1. Tweet 1 + Image 4 (hook — before/after)
2. Tweet 2 (the problem — text only)
3. Tweet 3 + Image 3 (architecture — three layers)
4. Tweet 4 + Image 1 (benchmarks — numbers)
5. Tweet 5 + Image 2 (killer feature — cortex_explain)
6. Tweet 6 (technical decisions — text only)
7. Tweet 7 (CTA + what's next — text only)
