#!/usr/bin/env python3
"""Minimal DataForSEO client for keyword research (name/SEO decisions).

Auth is HTTP Basic (login:password). Provide credentials via env:
    DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD
(or a combined DATAFORSEO_API_KEY, either "login:password" or its base64).
Never hardcode the key; never commit it. Requests go only to api.dataforseo.com.

CLI:
    dataforseo.py volume "kw one" "kw two" ...   # Google Ads search volume
    dataforseo.py ideas "seed keyword"           # related keyword ideas
    dataforseo.py whoami                          # auth check + balance
Options: --location <code, default 2840=US> --language <code, default en>
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request

BASE = "https://api.dataforseo.com/v3"


def _token() -> str:
    login = os.environ.get("DATAFORSEO_LOGIN")
    pw = os.environ.get("DATAFORSEO_PASSWORD")
    if login and pw:
        return base64.b64encode(f"{login}:{pw}".encode()).decode()
    combined = os.environ.get("DATAFORSEO_API_KEY", "")
    if combined:
        return combined if ":" not in combined else base64.b64encode(combined.encode()).decode()
    sys.exit("error: set DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD (or DATAFORSEO_API_KEY)")


def _post(path: str, payload: list) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Authorization": f"Basic {_token()}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))


def _opts(args: list[str]) -> tuple[list[str], int, str]:
    loc, lang, rest = 2840, "en", []
    it = iter(args)
    for a in it:
        if a == "--location":
            loc = int(next(it))
        elif a == "--language":
            lang = next(it)
        else:
            rest.append(a)
    return rest, loc, lang


def volume(args: list[str]) -> int:
    kws, loc, lang = _opts(args)
    if not kws:
        return _usage()
    r = _post("/keywords_data/google_ads/search_volume/live",
              [{"keywords": kws, "location_code": loc, "language_code": lang,
                "search_partners": False}])
    res = r["tasks"][0].get("result") or []
    rows = sorted(((x.get("keyword"), x.get("search_volume"),
                    str(x.get("competition") or "-"), round(x.get("cpc") or 0, 2))
                   for x in res), key=lambda x: (x[1] or -1), reverse=True)
    print(f"# cost ${r['tasks'][0].get('cost')}  loc={loc} lang={lang}")
    print(f"{'keyword':<30}{'vol/mo':>9}  {'comp':<8}{'cpc$':>7}")
    for kw, vol, comp, cpc in rows:
        print(f"{kw:<30}{(vol if vol is not None else 'n/a'):>9}  {comp:<8}{cpc:>7}")
    return 0


def ideas(args: list[str]) -> int:
    seeds, loc, lang = _opts(args)
    if not seeds:
        return _usage()
    r = _post("/keywords_data/google_ads/keywords_for_keywords/live",
              [{"keywords": seeds, "location_code": loc, "language_code": lang,
                "sort_by": "search_volume", "limit": 100}])
    res = [x for x in (r["tasks"][0].get("result") or []) if x.get("search_volume")]
    res.sort(key=lambda x: -(x.get("search_volume") or 0))
    print(f"# cost ${r['tasks'][0].get('cost')}  seed={seeds}")
    for x in res[:40]:
        print(f"{(x.get('search_volume') or 0):>9}  {str(x.get('competition') or '-'):<8}{x.get('keyword')}")
    return 0


def whoami(_args: list[str]) -> int:
    r = _post("/appendix/user_data", [{}]) if False else json.load(urllib.request.urlopen(
        urllib.request.Request(f"{BASE}/appendix/user_data",
                               headers={"Authorization": f"Basic {_token()}"}), timeout=25))
    t = r["tasks"][0]["result"][0]
    print("login:", t.get("login"), "| balance $:", (t.get("money") or {}).get("balance"))
    return 0


def _usage() -> int:
    print(__doc__)
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        return _usage()
    cmd, rest = sys.argv[1], sys.argv[2:]
    return {"volume": volume, "ideas": ideas, "whoami": whoami}.get(cmd, lambda _a: _usage())(rest)


if __name__ == "__main__":
    raise SystemExit(main())
