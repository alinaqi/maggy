"""Orchestration: plan -> decompose -> review each chunk -> synthesize hierarchically -> post.

Mega-PR strategy (the reason chunking is deterministic, not LLM-decided):
a huge PR cannot be reviewed — or synthesized — in a single context window. So we
ALWAYS decompose the changed files into bounded, coherent chunks (by feature area),
review each chunk with its OWN diff slice (never a truncated global diff), synthesize
each chunk independently, then merge the per-chunk verdicts deterministically. Every
LLM call therefore sees a bounded input, no matter how large the PR is.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from pydantic_ai.usage import UsageLimits

from .agents import build_chair, build_planner, build_refuter, build_reviewer
from .config import CHAIR, PRICING_KEY, available, cost_usd, load_env, load_skill
from .github import get_pr, get_pr_files, post_review
from .languages import detect_languages
from .models import ReviewChunk, Verdict
from .static_check import run_static_gate

# tool-using review agents make many requests (read_file/grep loops); the default
# request_limit of 50 is too low for a thorough reviewer/chair.
LIMITS = UsageLimits(request_limit=150)
# the planner plans from the embedded file LIST; a tight budget lets it spot-check
# one or two files without looping read_file calls (which balloon context on a mega PR).
PLANNER_LIMITS = UsageLimits(request_limit=8)
# a per-chunk reviewer reviews a bounded slice — 45 tool calls is plenty.
REVIEWER_LIMITS = UsageLimits(request_limit=45)
# wall-clock cap per agent — a hung/slow provider must not block a gather.
AGENT_TIMEOUT = 200

# --- mega-PR decomposition knobs ---------------------------------------------
SINGLE_PASS_FILES = 8       # <= this many files -> one chunk (the whole PR), full council
MAX_CHUNK_FILES = 8         # a chunk never reviews more than this many files at once
MAX_CHUNK_DIFF_CHARS = 20000  # per-chunk diff budget (fits a reviewer context comfortably)
PER_FILE_DIFF_CHARS = 4000  # per-file patch budget inside a chunk
PANEL_SIZE_MULTI = 2        # reviewers per chunk when the PR is split into many chunks
CONCURRENCY = 6             # max in-flight model calls (rate-limit safety on mega PRs)
REFUTE_CAP = 120            # adversarially verify at most this many blocking findings
FINDINGS_CAP = 40           # post at most this many findings inline; group the rest
# finding categories with a high false-positive rate on mega PRs (truncated-diff illusions):
# refute these FIRST so the cap never leaves one unverified.
_HIGH_FP = ("i18n", "translation", "german", "locale", "feature flag", "feature-flag",
            "not gated", "not feature", "unconditional", "missing test", "untranslat", "hardcoded")

# created per-run, inside the event loop (see run_review)
_SEM: asyncio.Semaphore | None = None
# model-cost-keys that hit a quota/429 wall this run — skipped for the rest of it
_DISABLED: set[str] = set()


def _is_quota_error(e) -> bool:
    s = str(e).lower()
    return any(t in s for t in ("429", "quota", "rate limit", "resource_exhausted", "exceeded"))


def _rec(usages, model_key, result):
    try:
        u = result.usage()
        usages.append((model_key, getattr(u, "input_tokens", 0) or 0,
                       getattr(u, "output_tokens", 0) or 0,
                       getattr(u, "cache_read_tokens", 0) or 0))
    except Exception:  # noqa: BLE001
        pass


async def _run_agent(agent, prompt, deps, limits, timeout=AGENT_TIMEOUT):
    """Run one agent with a wall-clock timeout under the global concurrency cap."""
    async def _go():
        return await asyncio.wait_for(agent.run(prompt, deps=deps, usage_limits=limits), timeout=timeout)
    if _SEM is not None:
        async with _SEM:
            return await _go()
    return await _go()


# Optional map of "owner/repo" -> local checkout path, for the static gate +
# deterministic FP filter. Maggy passes repo_path explicitly per request; this
# can be populated from config (review.repo_paths) for convenience.
REPO_PATHS: dict[str, Path] = {}


def _area_key(filename: str) -> str:
    """Coherent review-area key for a path: the feature/folder it belongs to."""
    p = filename.split("/")
    return "/".join(p[:4]) if len(p) >= 4 else (p[0] if p else "misc")


def decompose(files, langs) -> list[ReviewChunk]:
    """Deterministically split the PR into bounded, coherent review chunks.

    Small PRs become a single chunk (whole PR). Larger PRs are grouped by feature
    area and each oversized group is sliced to <= MAX_CHUNK_FILES. This guarantees
    the whole PR is covered and every chunk fits one reviewer context — regardless
    of how the planner LLM behaves on a huge file list.
    """
    names = [f["filename"] for f in files]
    if len(names) <= SINGLE_PASS_FILES:
        return [ReviewChunk(name="whole PR", focus="the entire change", files=names, languages=langs)]
    groups: dict[str, list[str]] = {}
    for fn in names:
        groups.setdefault(_area_key(fn), []).append(fn)
    chunks: list[ReviewChunk] = []
    for key, g in sorted(groups.items()):
        for j in range(0, len(g), MAX_CHUNK_FILES):
            sub = g[j:j + MAX_CHUNK_FILES]
            suffix = f" [{j // MAX_CHUNK_FILES + 1}]" if len(g) > MAX_CHUNK_FILES else ""
            clangs = detect_languages(sub) or langs
            chunks.append(ReviewChunk(name=key + suffix, focus="this area of the change",
                                      files=sub, languages=clangs))
    return chunks


def chunk_diff_text(files, chunk_files, per_file=PER_FILE_DIFF_CHARS, cap=MAX_CHUNK_DIFF_CHARS):
    """Diff text for ONLY this chunk's files — so a reviewer never judges on a
    truncated global diff (the bug that produced false positives on mega PRs)."""
    want = set(chunk_files)
    parts = []
    for f in files:
        if f["filename"] in want and f.get("patch"):
            parts.append(f"--- {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)}) ---\n"
                         f"{f['patch'][:per_file]}")
    return "\n\n".join(parts)[:cap]


def fallback_plan(files, langs):
    """Heuristic ReviewPlan when the planner LLM fails — risk only; decompose() owns chunking."""
    from .models import BlastRadius, ReviewPlan
    return ReviewPlan(
        blast_radius=BlastRadius(languages=langs, size="large", touches_auth_or_data=True,
                                 rationale="planner unavailable — heuristic risk assessment"),
        council_size=5, rounds=1, chunks=[],
        reason="heuristic fallback (planner failed/over-budget)")


async def review_one(name, factory, skill, focus, title, deps, on_log, usages, model_key,
                     with_tools=True, diff_text=""):
    if model_key in _DISABLED:  # this model already hit its quota wall this run
        return None
    rv = build_reviewer(factory(), skill, focus, with_tools=with_tools)
    prompt = (
        f"Review this PR: {title}. "
        + ("Use your tools (read_file/grep/get_diff) to VERIFY before flagging. "
           if with_tools else "Review the diff below; cite file:line. ")
        + ("Focus: " + focus if focus else "Review the whole change.")
    )
    if diff_text:
        prompt += f"\n\n--- DIFF (this review area) ---\n{diff_text}"
    try:
        res = await _run_agent(rv, prompt, deps, REVIEWER_LIMITS)
        _rec(usages, model_key, res)
        return res.output
    except Exception as e:  # noqa: BLE001 (TimeoutError included)
        if _is_quota_error(e):
            _DISABLED.add(model_key)
            on_log(f"[review] {model_key} hit quota/429 — disabling it for the rest of this run")
        else:
            on_log(f"[review] {name} FAILED: {type(e).__name__}: {str(e)[:160]}")
        return None


def _dedup_findings(verdicts):
    """Union findings across verdicts, deduped by (file, line, ~title). Preserves order + full detail."""
    seen, order = {}, []
    for v in verdicts:
        for fd in v.findings:
            k = (fd.file, fd.line, fd.title.strip().lower()[:60])
            if k not in seen:
                seen[k] = fd
                order.append(k)
    return [seen[k] for k in order]


def _deterministic_verdict(verdicts, note=""):
    merged = _dedup_findings(verdicts)
    blocked = any(fd.severity.value == "blocking" for fd in merged) or \
        any(v.decision == "changes_needed" for v in verdicts)
    summary = (note + " | ".join(v.summary[:140] for v in verdicts[:3])) if verdicts else (note or "no findings")
    return Verdict(decision="changes_needed" if blocked else "approve", summary=summary, findings=merged)


# --- deterministic false-positive filter (no LLM) -----------------------------
# The two FP classes that dominate mega-PR reviews are MECHANICALLY checkable, so we
# verify them in code instead of relying on a per-finding LLM (which is inconsistent):
#   1. "missing translation key" — grep the real locale JSON; if every key the file
#      uses resolves in BOTH en and de, the claim is false.
#   2. "not feature-flagged" on a sub-component — flag gating is an ENTRY-POINT concern;
#      a component that isn't a routed entry point doesn't get its own flag.
_RE_KEY = re.compile(r"""t\(\s*['"]([a-zA-Z0-9_.]+)['"]""")
_RE_I18N = re.compile(r"(i18n|translation|locale|missing.{0,15}key|de (locale|translation)|"
                      r"informal|not localized|missing 'de'|missing de)", re.I)
_RE_FLAG = re.compile(r"(feature.?flag|not gated|feature-flag|unconditional|not feature)", re.I)


def _flat_keys(path):
    keys = set()
    try:
        data = json.loads(Path(path).read_text())
    except Exception:  # noqa: BLE001
        return keys

    def walk(o, p=""):
        for k, v in o.items():
            walk(v, p + k + ".") if isinstance(v, dict) else keys.add(p + k)
    walk(data)
    return keys


def _resolves(key, ks):
    return key in ks or any(key + s in ks for s in ("_one", "_other", "_plural", "_zero", "_many"))


def _git_show(lp, ref, path):
    try:
        import subprocess
        r = subprocess.run(["git", "-C", str(lp), "show", f"{ref}:{path}"],
                           capture_output=True, text=True, timeout=15)
        return r.stdout if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def _routed(comp, router_text):
    # a component is a routed entry point if its name appears as a word in the router
    return bool(comp) and re.search(rf"\b{re.escape(comp)}\b", router_text) is not None


def _gated(comp, router_text):
    # is the component's mount inside a feature-flag conditional? (e.g. {zennyEnabled && <X/>})
    for m in re.finditer(rf"\b{re.escape(comp)}\b", router_text):
        ctx = router_text[max(0, m.start() - 400):m.start()]
        if re.search(r"Enabled\s*&&|useFeatureFlag|can_use_\w+\s*&&|FF_\w+\s*&&", ctx):
            return True
    return False


def deterministic_fp_filter(findings, local_path, on_log, base_ref=None):
    if not local_path:
        return findings, 0
    lp = Path(local_path)
    en = _flat_keys(lp / "libs/shared/services/translate/src/lib/locals/en/en.json")
    de = _flat_keys(lp / "libs/shared/services/translate/src/lib/locals/de/de.json")
    rp = lp / "apps/zenloop-app/src/Router.tsx"
    router = rp.read_text(errors="replace") if rp.exists() else ""
    # the same router on the BASE branch — to tell a NEW ungated route from a
    # pre-existing one (a finding "not feature-flagged" is only real for a NEW entry point).
    base_router = _git_show(lp, f"origin/{base_ref}", "apps/zenloop-app/src/Router.tsx") if base_ref else ""
    kept, dropped = [], 0
    for f in findings:
        if getattr(f.severity, "value", f.severity) != "blocking":
            kept.append(f)
            continue
        blob = f"{f.title} {f.detail}".lower()
        fpath = lp / f.file
        # (1) missing-translation-key FP: every zenny.* key the file uses resolves in both locales
        if en and de and _RE_I18N.search(blob) and "hardcod" not in blob and fpath.exists():
            used = {k for k in _RE_KEY.findall(fpath.read_text(errors="replace")) if k.startswith("zenny.")}
            if used and all(_resolves(k, en) and _resolves(k, de) for k in used):
                dropped += 1
                on_log(f"[det-fp] i18n FP dropped: {f.title[:55]} ({len(used)} keys all resolve en+de)")
                continue
        # (2) not-feature-flagged FP. Flag gating is an ENTRY-POINT concern, so the
        # finding is false unless this PR introduces a NEW ungated route:
        #   - component isn't routed at all  -> sub-component, inherits its host's gate
        #   - component is routed on the BASE branch too -> pre-existing, not new
        if router and _RE_FLAG.search(blob):
            comp = Path(f.file).stem
            if not _routed(comp, router):
                dropped += 1
                on_log(f"[det-fp] flag FP dropped: {f.title[:55]} ({comp} is a sub-component, not a route)")
                continue
            if base_router and _routed(comp, base_router):
                dropped += 1
                on_log(f"[det-fp] flag FP dropped: {f.title[:55]} ({comp} route pre-exists on base)")
                continue
            if _gated(comp, router):
                dropped += 1
                on_log(f"[det-fp] flag FP dropped: {f.title[:55]} ({comp} is already behind a feature flag)")
                continue
        kept.append(f)
    return kept, dropped


async def process_chunk(idx, chunk, council, skill, title, deps, on_log, usages, panel_size):
    """Review one chunk with a rotating panel on its OWN diff, then merge its panel.

    Per-chunk synthesis is DETERMINISTIC (dedup the panel's findings) — an LLM chair
    per chunk was redundant with the adversarial refute pass and was the dominant
    cost on a mega PR. The refute pass (later) is what verifies/kills false blockers."""
    panel = (council[idx % len(council):] + council[: idx % len(council)])[: min(panel_size, len(council))]
    cdiff = chunk_diff_text(deps.files, chunk.files)
    focus = (f"Area '{chunk.name}': {chunk.focus}. Files: {', '.join(chunk.files[:25])}. "
             "Only flag issues in THESE files; the diff for them is below.")
    revs = await asyncio.gather(*[
        review_one(f"{n}@{chunk.name}", f, skill, focus, title, deps, on_log, usages,
                   PRICING_KEY.get(n, ""), tools, cdiff)
        for (n, f, _l, tools) in panel])
    verdicts = [v for v in revs if v]
    if not verdicts:
        on_log(f"[chunk] {chunk.name}: no reviewer verdicts")
        return None
    cv = _deterministic_verdict(verdicts)
    nblock = sum(1 for fd in cv.findings if fd.severity.value == "blocking")
    on_log(f"[chunk] {chunk.name}: {len(verdicts)} reviews -> {len(cv.findings)} findings ({nblock} blocking)")
    return cv


async def final_summary(chunk_verdicts, skill, chair_factory, chair_key, deps, usages, on_log):
    """A short overall summary across chunks. Findings are merged deterministically
    (not regenerated), so this call stays tiny even with dozens of chunks."""
    text = "\n\n".join(f"### area {i + 1} ({v.decision})\n{v.summary}"
                       for i, v in enumerate(chunk_verdicts))[:8000]
    chair = build_chair(chair_factory(), skill, with_tools=False)  # prose only — no file reads
    try:
        res = await _run_agent(
            chair, "Write ONE 2-4 sentence overall verdict summary for the PR author from these "
            "per-area summaries. Do not list findings; they are aggregated separately.\n\n" + text,
            deps, PLANNER_LIMITS, timeout=AGENT_TIMEOUT)
        _rec(usages, chair_key, res)
        return res.output.summary
    except Exception:  # noqa: BLE001
        return " | ".join(v.summary[:120] for v in chunk_verdicts[:4])


async def run_review(owner, repo, num, dry_run=True, repo_path=None, on_log=print, token=None):
    global _SEM
    load_env()
    from .tools import ReviewDeps  # imported here so config.load_env() ran first

    _SEM = asyncio.Semaphore(CONCURRENCY)
    _DISABLED.clear()
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("no GitHub token — set review.github_token, pass an override, or export GITHUB_TOKEN")
    pr = get_pr(token, owner, repo, num)
    files = get_pr_files(token, owner, repo, num)
    head = pr["head"]["sha"]
    langs = detect_languages([f["filename"] for f in files])
    lp = Path(repo_path) if repo_path else REPO_PATHS.get(f"{owner}/{repo}")
    deps = ReviewDeps(token, owner, repo, head, files, local_path=lp if lp and Path(lp).exists() else None)

    # DETERMINISTIC STATIC GATE — runs the real compiler/linter concurrently with the
    # council (the council reads diffs but never compiles, so it misses undefined refs,
    # type errors, syntax errors). Its findings are ground truth -> skip refute.
    static_task = asyncio.create_task(run_static_gate(deps, langs, on_log))

    roster = available()
    if not roster:
        raise SystemExit("no model providers available (set keys in revir/.env)")
    by_name = {n: f for n, f, _lbl, _t in roster}
    chair_name = CHAIR if CHAIR in by_name else roster[0][0]
    chair_factory = by_name[chair_name]
    chair_key = PRICING_KEY.get(chair_name, "")
    on_log(f"[plan] {len(files)} files, languages={langs}, roster={[n for n, _, _, _ in roster]}")

    usages = []  # (model_key, in, out, cached) per agent run — for cost

    # 1) PLAN — blast radius + council size (decompose() owns the actual chunking)
    file_list = "\n".join(f"  {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
                          for f in files)[:9000]
    planner = build_planner(chair_factory(), with_tools=False)  # plan from the file list; no read loops
    try:
        pres = await _run_agent(planner,
            f"Plan the review for PR #{num}: {pr.get('title')} "
            f"(+{pr.get('additions')}/-{pr.get('deletions')}, {pr.get('changed_files')} files). "
            f"Languages: {langs}.\n\nCHANGED FILES:\n{file_list}\n\n"
            "Assess blast radius + council size from this file list alone. "
            "(Chunking is handled deterministically — leave chunks empty.)",
            deps, PLANNER_LIMITS)
        _rec(usages, chair_key, pres)
        plan = pres.output
    except Exception as e:  # noqa: BLE001 — never crash the run on a planner failure
        on_log(f"[plan] planner failed ({type(e).__name__}: {str(e)[:80]}); using heuristic plan")
        plan = fallback_plan(files, langs)
    skill = load_skill(plan.blast_radius.languages or langs)

    # 2) DECOMPOSE — deterministic, always (the mega-PR backbone)
    chunks = decompose(files, langs)
    # Reviewers PROPOSE, the chair/refuter DISPOSE: keep the (premium) chair model out
    # of the bulk reviewer council so it isn't double-billed doing tool-heavy chunk
    # reviews — on a mega PR that one change is the difference between ~$2.4 and ~$1.
    reviewers = [r for r in roster if r[0] != chair_name] or roster
    council = reviewers[: max(1, min(plan.council_size, len(reviewers)))]
    panel_size = len(council) if len(chunks) == 1 else min(PANEL_SIZE_MULTI, len(council))
    title = pr.get("title", "")
    on_log(f"[plan] blast={plan.blast_radius.size} council={len(council)} chunks={len(chunks)} "
           f"panel/chunk={panel_size} — {plan.reason[:70]}")

    # 3) REVIEW + deterministic per-chunk merge, all chunks concurrently (bounded by _SEM)
    chunk_results = await asyncio.gather(*[
        process_chunk(i, ch, council, skill, title, deps, on_log, usages, panel_size)
        for i, ch in enumerate(chunks)])
    chunk_verdicts = [cv for cv in chunk_results if cv]
    on_log(f"[review] {len(chunk_verdicts)}/{len(chunks)} chunks produced a verdict")

    # 4) MERGE chunks -> one final verdict. Findings are deduped deterministically;
    #    only the short prose summary is LLM-written, so this step never overflows.
    if not chunk_verdicts:
        final = Verdict(decision="changes_needed",
                        summary="Review could not be completed — no chunk produced a verdict.", findings=[])
    else:
        merged = _dedup_findings(chunk_verdicts)
        blocked = any(fd.severity.value == "blocking" for fd in merged)
        summ = await final_summary(chunk_verdicts, skill, chair_factory, chair_key, deps, usages, on_log)
        final = Verdict(decision="changes_needed" if blocked else "approve",
                        summary=summ, findings=merged)

    # 4b) DETERMINISTIC FP FILTER — kill mechanically-checkable false positives (no LLM)
    base_ref = (pr.get("base") or {}).get("ref")
    final.findings, det_dropped = deterministic_fp_filter(final.findings, deps.local_path, on_log, base_ref)
    if det_dropped:
        on_log(f"[det-fp] dropped {det_dropped} mechanically-verified false positive(s)")
        if not any(f.severity.value == "blocking" for f in final.findings):
            final.decision = "approve"

    # 5) REFUTE — adversarially verify every remaining blocking finding (kills the rest)
    blocking = [f for f in final.findings if f.severity.value == "blocking"]
    refuter_factory = by_name.get("Hopper") or chair_factory  # strong, tool-capable
    refuter_key = PRICING_KEY.get("Hopper", chair_key) if "Hopper" in by_name else chair_key

    async def refute(fd):
        r = build_refuter(refuter_factory())
        claim = (f"DISPROVE this BLOCKING finding if you can:\nTitle: {fd.title}\n"
                 f"Location: {fd.file}:{fd.line or '-'}\nDetail: {fd.detail}\n"
                 f"Reviewer's evidence: {fd.evidence}")
        try:
            out = await _run_agent(r, claim, deps, LIMITS)
            _rec(usages, refuter_key, out)
            return fd, out.output
        except Exception:  # noqa: BLE001 — on refuter error, keep the finding (fail safe)
            return fd, None

    if blocking:
        # Refute high-false-positive categories FIRST (truncated-diff illusions like
        # "missing translation" / "not feature-flagged"), so the cap never leaves one
        # of those unverified. Remainder is kept (fail-safe: unverified blockers stay).
        def _fp_first(fd):
            blob = f"{fd.title} {fd.detail}".lower()
            return 0 if any(t in blob for t in _HIGH_FP) else 1
        blocking.sort(key=_fp_first)
        to_refute, unrefuted = blocking[:REFUTE_CAP], blocking[REFUTE_CAP:]
        survived, dropped = [], 0
        for fd, ref in await asyncio.gather(*[refute(f) for f in to_refute]):
            if ref and ref.refuted:
                dropped += 1
                on_log(f"[refute] DROPPED false positive: {fd.title[:60]} — {ref.reason[:90]}")
            else:
                survived.append(fd)
        survived += unrefuted
        nits = [f for f in final.findings if f.severity.value == "nit"]
        final.findings = survived + nits
        notes = []
        if dropped:
            notes.append(f"{dropped} flagged blocker(s) dropped after adversarial verification")
        if unrefuted:
            notes.append(f"{len(unrefuted)} blocker(s) kept un-individually-verified (refute cap {REFUTE_CAP})")
        if notes:
            final.summary = f"_({'; '.join(notes)}.)_ " + final.summary
        if not survived:
            final.decision = "approve"
        on_log(f"[refute] {len(survived)}/{len(blocking)} blocking findings survived "
               f"({len(to_refute)} refuted, {len(unrefuted)} over cap)")

    # STATIC GATE — merge deterministic compiler/linter errors. Ground truth, so they
    # bypass the FP filter AND the refute pass, and they force changes_needed.
    try:
        static_findings = await static_task
    except Exception as e:  # noqa: BLE001
        on_log(f"[static] gate errored ({type(e).__name__}); continuing without it")
        static_findings = []
    if static_findings:
        final.findings = static_findings + final.findings
        final.decision = "changes_needed"
        final.summary = (f"_({len(static_findings)} deterministic build/type error(s) caught by the "
                         "static gate — these break the build and must be fixed.)_ " + final.summary)

    # When findings are overwhelming (pervasive debt on a mega PR), cap what we post
    # inline and fold the rest into a grouped, per-file summary so the output stays
    # actionable instead of being hundreds of comments.
    if len(final.findings) > FINDINGS_CAP:
        def _rank(f):  # static (ground-truth) first, then blocking, then nits
            if f.evidence and "static analysis" in f.evidence:
                return 0
            return 1 if f.severity.value == "blocking" else 2
        kept = sorted(final.findings, key=_rank)[:FINDINGS_CAP]
        overflow = [f for f in final.findings if f not in kept]
        by_file: dict[str, int] = {}
        for f in overflow:
            by_file[f.file] = by_file.get(f.file, 0) + 1
        top = sorted(by_file.items(), key=lambda kv: -kv[1])[:12]
        grouped = "; ".join(f"{fp} ({n})" for fp, n in top)
        final.summary += (f"\n\n**+{len(overflow)} more findings across {len(by_file)} files** "
                          f"(showing {FINDINGS_CAP} inline). Most-affected: {grouped}.")
        final.findings = kept
        on_log(f"[cap] posting {len(kept)} findings inline; grouped {len(overflow)} into summary")

    # cost accounting (cache_read discounted — see config.cost_usd)
    by_model, total_in, total_out, total_cached, total_cost = {}, 0, 0, 0, 0.0
    for k, i, o, cr in usages:
        c = cost_usd(k, i, o, cr)
        m = by_model.setdefault(k or "?", [0, 0, 0, 0.0])
        m[0] += i
        m[1] += o
        m[2] += cr
        m[3] += c
        total_in += i
        total_out += o
        total_cached += cr
        total_cost += c
    on_log(f"[cost] ~${total_cost:.3f}  ({total_in / 1000:.0f}k in ({total_cached / 1000:.0f}k cached) "
           f"+ {total_out / 1000:.0f}k out over {len(usages)} model runs)")
    cost = {"total_usd": round(total_cost, 4), "input_tokens": total_in, "output_tokens": total_out,
            "cached_tokens": total_cached, "runs": len(usages),
            "by_model": {k: {"in": v[0], "out": v[1], "cached": v[2], "usd": round(v[3], 4)}
                         for k, v in by_model.items()}}

    # 6) POST
    meta = {"blast": plan.blast_radius.size, "council": len(council), "chunks": len(chunks)}
    result = post_review(token, owner, repo, num, final.decision, final.summary, final.findings,
                         files, dry_run=dry_run, meta=meta)
    return {"plan": plan, "chunks": chunks, "verdicts": chunk_verdicts,
            "final": final, "post": result, "cost": cost}
