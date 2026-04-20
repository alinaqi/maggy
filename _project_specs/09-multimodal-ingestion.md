# Spec 09: Multimodal Ingestion (Optional Graphify-Style Extension)

**Status:** pending
**Priority:** Tier 3 (frontier / optional)
**Effort:** Large

## Context

Our stack is code-only. Some repos carry essential context in non-code artifacts:

- Product specs in PDFs or Google Docs exports
- Architecture diagrams in PNG / Miro / whiteboard photos
- Engineering demos in MP4
- Research papers in PDF

When an autonomous agent works on such a repo, it currently ignores these artifacts. That's a real gap — the agent makes code decisions without knowing the intent captured in the diagrams or docs.

Graphify (github.com/safishamsi/graphify) solves this: it ingests docs, images, audio, and video into the same knowledge graph as code. We don't need to rebuild their work — we can adopt their approach as an optional extension to claude-bootstrap.

**This spec is optional** — only valuable if your repos actually carry non-code context. Most don't.

## Goal

Let claude-bootstrap ingest non-code artifacts into the iCPG graph so agents can reason about code + docs + images in the same queries.

## Approach

### Step 1 — Artifact node type

Extend iCPG with a new node:

```
Artifact {
  id, path, kind, content_hash, ingested_at,
  extracted_concepts: []    // concept strings
}
```

Kinds: `pdf`, `markdown`, `image`, `diagram`, `video`, `audio`, `slides`.

### Step 2 — Ingestion pipeline

`icpg ingest <path>` — one command, pluggable extractors:

- `pdf_extractor.py` — text via `pypdf` or `pdfplumber`, then LLM to extract key concepts
- `markdown_extractor.py` — parse headings, blockquotes, pull out "key decision" patterns
- `image_extractor.py` — Claude multimodal: "describe this diagram; list entities and relationships"
- `video_extractor.py` — `faster-whisper` transcription with domain-aware prompt, then concept extraction
- `audio_extractor.py` — same as video, skip video decode

Each extractor emits concept nodes + relationships back into iCPG using the existing edge vocabulary:
- `DESCRIBES` — Artifact → Symbol / Reason (this doc describes this code)
- `MENTIONS` — Artifact → Concept (looser reference)
- `DECIDES` — Artifact → Reason (this doc made an architectural decision that became an intent)

### Step 3 — `.icpgignore` for ingest paths

Respect a per-project `.icpgignore` like graphify's `.graphifyignore`, using `.gitignore` syntax. Default excludes: `node_modules/`, `dist/`, `.venv/`, `*.generated.*`, binary builds.

### Step 4 — Incremental refresh

Track content hashes per artifact. Re-ingest only when hash changes. Bulk re-ingest via `icpg ingest --refresh`.

### Step 5 — Extend pre-task queries

Add a 5th canonical query:

```bash
icpg query docs "<topic>"   # Find artifacts relevant to this topic
```

Returns: artifact paths, extracted concepts, relationships to code symbols.

The PreToolUse hook includes this in the injected context when the agent is about to write code in a scope touched by `DESCRIBES` edges.

### Step 6 — Transparent honesty about inference

Adopt graphify's `EXTRACTED` / `INFERRED` / `AMBIGUOUS` edge labeling. PDF text → EXTRACTED. Image concept → INFERRED with confidence. Whiteboard smudged text → AMBIGUOUS, flagged for review.

### Step 7 — Cost control

LLM-based extractors (images, video transcripts) are expensive. Respect Spec 06 budgets. `icpg ingest` without a budget flag runs only the free extractors (markdown, PDF text). Image / video / audio require `--enable-llm` explicit flag.

### Step 8 — Distribution

Ship this as a **separate installable package** — `claude-bootstrap-multimodal` on PyPI. Base claude-bootstrap stays code-only. Users opt in:

```bash
pip install claude-bootstrap-multimodal
icpg ingest docs/ specs/
```

## Integration points

- `scripts/icpg/models.py` — `Artifact`, new edge types (`DESCRIBES`, `MENTIONS`, `DECIDES`)
- `scripts/icpg/ingest/` — new package (could live in a separate repo)
- `scripts/icpg/__main__.py` — `ingest` subcommand
- `skills/icpg/SKILL.md` — document the 5th pre-task query
- `skills/multimodal/SKILL.md` — new skill describing when to use ingestion

## Success criteria

1. `icpg ingest docs/` processes markdown + PDF without LLM and creates artifact nodes
2. `icpg ingest --enable-llm specs/` processes images and videos, with the budget flag respected
3. Pre-task queries surface relevant documentation when the agent is about to modify code touched by `DESCRIBES` edges
4. Re-ingestion only processes changed files (hash-based cache)
5. Base claude-bootstrap doesn't require multimodal deps to work — installed separately

## Depends on

- Spec 06 (budget) — LLM extractors must respect budget caps

## Alternative: adopt graphify directly

Instead of building this, we could document "for multimodal, run graphify alongside" and provide a conversion tool that imports graphify's `graph.json` into iCPG as Artifact nodes. This is faster to ship and avoids duplicating graphify's work.

**Recommendation:** ship the conversion tool first (1-2 days of work), observe adoption, build native ingestion only if real demand emerges.
