"""The agency -> org crosswalk, measured against the real database.

⚠⚠ TWO SQL TEXTS FOR ONE RULE CANNOT BE PINNED BY LOOKING ALIKE. The unit
guards in `api/tests/test_agency_crosswalk.py` assert the SHAPE — one owner, the
exact tier before the alias tier, no endpoint re-spelling it. This asserts the
VALUE: that the batch path and the single-name path return the same org for
every stored agency string, and that the surfaces which link an agency actually
resolve one.

⚠ Run from the repo root with the local stack up:
    python3 scripts/headless/verify_agency_crosswalk.py
"""
import json
import subprocess
import sys
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8581"

AGREE = r'''
import asyncio, sys
sys.path.insert(0, "/app")
from modules import autoload  # noqa
import routers.oce as oce

async def main():
    rows = await oce.PostgresModelAsync.select_safe(
        "SELECT DISTINCT agency FROM contracts WHERE agency IS NOT NULL AND agency <> ''", [])
    names = [r["agency"] for r in rows]
    batch = await oce._resolve_org_ids(names)
    bad = []
    for n in names:
        one = await oce._resolve_org_id(n)
        if one != batch.get((n or "").strip()):
            bad.append((n, one, batch.get((n or "").strip())))
    print("NAMES", len(names))
    print("RESOLVED", sum(1 for n in names if batch.get(n.strip()) is not None))
    print("DISAGREE", len(bad))
    for b in bad[:5]:
        print("BAD", b)
asyncio.run(main())
'''


def _api(path):
    with urllib.request.urlopen(API + path, timeout=120) as f:
        return json.load(f)


def main():
    problems = []

    # ---- the two paths agree, name by name -------------------------------
    p = subprocess.run(["docker", "compose", "exec", "-T", "api",
                        "python", "-c", AGREE], capture_output=True, text=True)
    out = {}
    for line in p.stdout.split("\n"):
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0] in ("NAMES", "RESOLVED", "DISAGREE"):
            out[parts[0]] = int(parts[1])
    if not out:
        print("could not run the in-container comparison:", p.stderr[-300:])
        return 2
    # ⚠ Non-vacuity: zero disagreements over zero names is not agreement.
    if out.get("NAMES", 0) < 20:
        problems.append(f"only {out.get('NAMES')} agency strings compared — the query moved")
    if out.get("DISAGREE", 1) != 0:
        problems.append(f"{out['DISAGREE']} names resolve differently in the batch "
                        f"and single-name paths")
    print(f"  {out.get('NAMES')} agency strings, {out.get('RESOLVED')} resolved, "
          f"{out.get('DISAGREE')} disagreements")

    # ---- the surfaces that link an agency actually resolve one -----------
    checks = [
        ("/oce/agencies", lambda d: [r for r in (d.get("agencies") or d)],
         lambda r: r.get("org_id")),
        ("/oce/digital-reform/masters", lambda d: d["rows"], lambda r: r.get("org_id")),
        ("/oce/licenses/data", lambda d: d["content"]["by_agency"],
         lambda r: r.get("org_id") if r.get("named") else True),
    ]
    for path, rows_of, org_of in checks:
        rows = rows_of(_api(path))
        got = sum(1 for r in rows if org_of(r))
        print(f"  {path:34} {got}/{len(rows)} resolve")
        if not rows:
            problems.append(f"{path} returned no rows — nothing was measured")
        elif got < len(rows):
            # ⚠ Named as a WARNING, not a failure: an unresolved agency is a
            # legitimate state (the seed is curated, not exhaustive). What must
            # not happen is a REGRESSION, so the floor is the measured level.
            problems.append(f"{path} resolves {got} of {len(rows)} — was 100% on 2026-09-16")

    ch = _api("/oce/digital-reform/all?page=1")["charts"]["agencies"]
    got = sum(1 for o in ch.get("org_ids") or [] if o)
    print(f"  overview agency chart              {got}/{len(ch['labels'])} resolve")
    if got < len(ch["labels"]):
        problems.append(f"the overview agency chart resolves {got} of {len(ch['labels'])}")
    # ⚠ The chart must serve FULL names: a 40-char cut matches no org and no alias.
    if any(len(l) == 40 for l in ch["labels"]):
        problems.append("an agency label is exactly 40 chars — it looks truncated again")

    print()
    if problems:
        print("PROBLEMS:")
        for x in problems:
            print("  -", x)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
