"""GitHub API: fetch PR data + post a review with inline line comments."""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"


def gh(token, path, accept="application/vnd.github+json", method="GET", body=None):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "revir-agentic-reviewer",
            **({"Content-Type": "application/json"} if body else {}),
        },
    )
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return raw if accept.endswith("diff") else json.loads(raw or b"{}")


def get_pr(token, owner, repo, num):
    return gh(token, f"/repos/{owner}/{repo}/pulls/{num}")


def get_pr_files(token, owner, repo, num):
    out, page = [], 1
    while page <= 40:
        batch = gh(token, f"/repos/{owner}/{repo}/pulls/{num}/files?per_page=100&page={page}")
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def get_file_at(token, owner, repo, path, ref):
    d = gh(token, f"/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}?ref={ref}")
    return base64.b64decode(d.get("content", "")).decode("utf-8", "replace")


def valid_comment_lines(patch: str) -> set[int]:
    """New-file (RIGHT) line numbers that appear in the diff hunks — the only
    lines GitHub will accept an inline review comment on."""
    lines, newno = set(), None
    for ln in (patch or "").splitlines():
        h = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
        if h:
            newno = int(h.group(1))
            continue
        if newno is None:
            continue
        if ln.startswith("+"):
            lines.add(newno)
            newno += 1
        elif ln.startswith("-"):
            pass
        else:
            newno += 1
    return lines


def _sev(fnd):
    return getattr(fnd.severity, "value", fnd.severity)


# CodeRabbit-style severity badge line per finding
_BADGE = {
    "blocking": "_⚠️ Potential issue_ | _🔴 Blocking_",
    "nit": "_🧹 Nitpick_ | _🟡 Minor_",
}


def _finding_body(fnd):
    """A single inline comment, formatted like CodeRabbit: badge · bold title ·
    explanation · collapsible suggested fix · collapsible evidence."""
    body = f"{_BADGE.get(_sev(fnd), '_💡 Note_')}\n\n**{fnd.title}**\n\n{fnd.detail}"
    if fnd.suggestion:
        body += ("\n\n<details>\n<summary>💡 Suggested fix</summary>\n\n"
                 f"{fnd.suggestion}\n\n</details>")
    if fnd.evidence:
        body += ("\n\n<details>\n<summary>🔎 Evidence (what revir verified)</summary>\n\n"
                 f"{fnd.evidence}\n\n</details>")
    return body


def _area_key(filename):
    p = filename.split("/")
    return "/".join(p[:4]) if len(p) >= 4 else (p[0] if p else "misc")


def _changes_table(files):
    areas = {}
    for f in files:
        a = areas.setdefault(_area_key(f["filename"]), [0, 0, 0])
        a[0] += 1
        a[1] += f.get("additions", 0)
        a[2] += f.get("deletions", 0)
    rows = "\n".join(f"| `{k}` | {v[0]} | +{v[1]}/−{v[2]} |"
                     for k, v in sorted(areas.items(), key=lambda kv: -kv[1][1])[:25])
    extra = "" if len(areas) <= 25 else f"\n\n_…and {len(areas) - 25} more areas._"
    return "| Area | Files | Lines |\n|---|--:|--:|\n" + rows + extra


def _walkthrough_body(decision, summary, findings, files, overflow, meta):
    meta = meta or {}
    verdict = ("✅ **Approve**" if decision == "approve"
               else "🛑 **Changes requested**")
    nblock = sum(1 for f in findings if _sev(f) == "blocking") + sum(
        1 for o in overflow if o[0] == "blocking")
    nnit = sum(1 for f in findings if _sev(f) == "nit") + sum(1 for o in overflow if o[0] == "nit")
    bits = [f"blast radius **{meta.get('blast', '?')}**", f"council **{meta.get('council', '?')}**",
            f"**{meta.get('chunks', '?')}** review areas",
            f"**{nblock}** blocking · **{nnit}** nits"]
    head = ("## 🔎 revir feedback\n\n"
            f"> {verdict}  ·  " + "  ·  ".join(bits) + "\n\n"
            "<details open>\n<summary>📝 Walkthrough</summary>\n\n" + summary + "\n\n</details>\n\n"
            "<details>\n<summary>📂 Changes</summary>\n\n" + _changes_table(files) + "\n\n</details>")
    if overflow:
        items = "\n".join(o[1] for o in overflow)
        head += (f"\n\n<details>\n<summary>📌 {len(overflow)} more finding(s) outside the diff</summary>"
                 f"\n\n{items}\n\n</details>")
    head += "\n\n<sub>— revir · agentic council review</sub>"
    return head


def post_review(token, owner, repo, num, decision, summary, findings, files, dry_run=False, meta=None):
    """Post a review: CodeRabbit-style walkthrough body + inline comments for findings
    on diff lines (the rest folded into a collapsible overflow). decision: 'approve' | 'changes_needed'."""
    valid = {f["filename"]: valid_comment_lines(f.get("patch", "")) for f in files}
    inline, overflow = [], []
    for fnd in findings:
        path, line = fnd.file, fnd.line
        if line and path in valid and line in valid[path]:
            inline.append({"path": path, "line": line, "side": "RIGHT", "body": _finding_body(fnd)})
        else:
            tag = "🔴" if _sev(fnd) == "blocking" else "🟡"
            loc = f"`{path}`" + (f":{line}" if line else "")
            overflow.append((_sev(fnd), f"- {tag} {loc} — **{fnd.title}**: {fnd.detail}"))

    event = "APPROVE" if decision == "approve" else "COMMENT"
    head = _walkthrough_body(decision, summary, findings, files, overflow, meta)

    if dry_run:
        return {"dry_run": True, "event": event, "inline": len(inline), "overflow": len(overflow), "body": head}
    payload = {"event": event, "body": head}
    if inline:
        payload["comments"] = inline
    try:
        gh(token, f"/repos/{owner}/{repo}/pulls/{num}/reviews", method="POST", body=payload)
        return {"event": event, "inline": len(inline), "overflow": len(overflow)}
    except urllib.error.HTTPError as e:  # noqa: F821
        detail = e.read().decode("utf-8", "replace")[:300]
        # self-approval refused, or a bad inline line slipped through -> retry as plain comment
        payload2 = {"event": "COMMENT", "body": head + (f"\n\n_(inline comments dropped: {detail})_" if detail else "")}
        gh(token, f"/repos/{owner}/{repo}/pulls/{num}/reviews", method="POST", body=payload2)
        return {"event": "COMMENT", "inline": 0, "overflow": len(overflow), "fallback": detail}
