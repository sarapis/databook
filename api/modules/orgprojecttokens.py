"""wegov_orgs id -> the token identifying its capital projects in the plan text.

⚠⚠ WHY. Some organizations deliver capital work without ever being its MANAGING or
SPONSORING agency, so they hold no row in `capitalprojectsdollarscomp` under their
own id and their Capital Projects tab is empty. The projects exist — carried on the
capital budget of the agency that contracts them.

⚠⚠ WORD BOUNDARY, NEVER A BARE SUBSTRING. Measured 2026-09-02: `%EDC%` matches
**INCLUDEDCITY** (INCLUDED + CITY run together in a DDC scope text) and pulls in 11
unrelated road-reconstruction projects — 26 projects by substring against 15 with
`\\mEDC\\M`. A three-letter token is exactly the case this repo keeps paying for.

⚠ TEXT EVIDENCE, NOT AN AUTHORITATIVE LINK. This is the plan description NAMING the
organization. Good enough to show with the basis stated; not good enough to assert
that the organization owns the project. The consuming page says so.
"""
import csv
import os

_SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'seed', 'org_capital_project_tokens.csv')

_by_org = None


def _load(logger=None):
    global _by_org
    if _by_org is not None:
        return _by_org
    try:
        with open(_SEED, newline='', encoding='utf-8') as fh:
            # ⚠ Skip `#` lines — every api/seed file carries a comment header.
            rows = list(csv.DictReader(l for l in fh if not l.lstrip().startswith('#')))
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.error("org capital-project token seed unreadable (%s): %s", _SEED, exc)
        _by_org = {}
        return _by_org
    out = {}
    for r in rows:
        oid = str(r.get('org_id') or '').strip()
        tok = (r.get('token') or '').strip()
        # ⚠ A token must be alphanumeric: it is interpolated into a regex, so a
        # metacharacter would either break the query or silently widen it.
        if oid.isdigit() and tok and tok.isalnum():
            out[int(oid)] = tok
    _by_org = out
    return _by_org


def token_for(org_id, logger=None):
    try:
        oid = int(org_id)
    except (TypeError, ValueError):
        return None
    return _load(logger).get(oid)
