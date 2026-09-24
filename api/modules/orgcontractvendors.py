"""wegov_orgs id -> the EXACT `contracts.vendor_name` that org is paid under.

⚠⚠ WHY. Some bodies on the org register are not City agencies and hold no capital
budget line, so every agency-keyed dataset renders empty for them — yet they DO
appear in the procurement record, as VENDORS. The org profile could not show that:
it is keyed on `wegov-org-id`, and a contract identifies its vendor only by
free-text `vendor_name`.

⚠ THREE ROUTES DO NOT REACH THEM, measured 2026-09-02 — which is why this is a
curated seed rather than a derivation:
  1. `org_vendor_crosswalk` keys on a PASSPort supplier id, and NYCEDC has NO
     PASSPort vendor record at all.
  2. Exact name match fails — "Economic Development Corporation" (register) vs
     "NEW YORK CITY ECONOMIC DEVELOPMENT CORPORATION" (contracts). Only 17 live
     orgs match a vendor name exactly.
  3. ⚠⚠ Fuzzy is actively WRONG: the crosswalk's only held candidate for org
     170010998 is QUEENS ECONOMIC DEVELOPMENT CORPORATION — a different
     organization, correctly quarantined in `candidate_supplier_id` so it cannot
     reach a page (#146 working as intended). Do not replace this with similarity.

⚠ EXACT MATCH ONLY, never a LIKE. `%ECONOMIC DEVELOPMENT CORP%` matches SEVEN
organizations and NYCEDC is 24 of those 163 contracts; a substring would attribute
another nonprofit's $31M to it.
"""
import csv
import os

_SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'seed', 'org_contract_vendors.csv')

_by_org = None


def _load(logger=None):
    global _by_org
    if _by_org is not None:
        return _by_org
    try:
        with open(_SEED, newline='', encoding='utf-8') as fh:
            # ⚠ Skip `#` lines — every file in api/seed/ carries a comment header,
            # and a parser that does not expect one reads it as a data row.
            rows = list(csv.DictReader(l for l in fh if not l.lstrip().startswith('#')))
    except Exception as exc:  # noqa: BLE001
        # ERROR, not warning: an absent seed silently removes the only view of
        # these organizations' City work, and an empty map is indistinguishable
        # from "no org does contract work".
        if logger:
            logger.error("org contract-vendor seed unreadable (%s): %s", _SEED, exc)
        _by_org = {}
        return _by_org
    out = {}
    for r in rows:
        oid = str(r.get('org_id') or '').strip()
        name = (r.get('vendor_name') or '').strip()
        if oid.isdigit() and name:
            out.setdefault(int(oid), []).append(name)
    _by_org = out
    return _by_org


def vendor_names_for(org_id, logger=None):
    """Exact contract vendor names for an org id, or []."""
    try:
        oid = int(org_id)
    except (TypeError, ValueError):
        return []
    return list(_load(logger).get(oid, []))


def rows(logger=None):
    return dict(_load(logger))
