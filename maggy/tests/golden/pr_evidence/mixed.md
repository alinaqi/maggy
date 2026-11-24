## Evidence

- Ticket: `AWG-42`
- Spec version: `7`
- Tested commit: `0123456789abcdef0123456789abcdef01234567`
- Gate: closed (a required criterion failed or the review has blocking findings)

| Criterion | Verdict | Check(s) | Evidence | Detail | Artifacts |
|---|---|---|---|---|---|
| AC1 | passed | functional | unit | test_ac1 passed | log `attempts/A1/verify/functional/AC1/run.log` (sha256:dc51b8c96c2d) |
| AC2 | failed | functional | e2e | test_ac2: failed: assert 100 == 90 | - |
| AC3 | blocked | visual mobile | visual | chromium is not available | - |
| AC4 | pending | vision desktop | visual | no vision backend available | - |
| AC5 | not applicable | - | manual | recorded as not applicable by a human | - |
| Release impact | - | - | - | UI-only fix; pricing rules and API contract preserved. | - |

### Review council

- blocking `calc.py:3` discount applied twice: apply() runs the rule again

### Verification gaps

- [AC2] functional log withheld from the PR: secret scan (github token)
- [AC3] blocked: chromium is not available
- [AC4] pending: no vision backend available
